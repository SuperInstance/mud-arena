```c
/*****************************************************************************************
 * mud_arena.cu
 *
 * GPU‑accelerated MUD simulation engine.
 *
 * Compile (GPU):   nvcc -O3 -arch=sm_87 -o mud-arena mud_arena.cu
 * Compile (CPU):   gcc -O3 -DNO_CUDA -o mud-arena-cpu mud_arena.cu
 *
 * Run example:
 *   ./mud-arena --agents 1024 --rooms 256 --turns 100 --scenarios 20
 *
 * The code follows the architecture described in the prompt:
 *   - One CUDA block   = one room
 *   - One CUDA thread  = one avatar in that room
 *   - Shared memory per block holds the room state
 *   - Global memory holds agents, scripts, scenario data
 *
 * CPU fallback versions are provided for systems without a CUDA runtime.
 *****************************************************************************************/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#ifndef NO_CUDA
#include <cuda_runtime.h>
#include <curand_kernel.h>
#endif

/* -------------------------------------------------------------------------- *
 *  Constants
 * -------------------------------------------------------------------------- */
#define MAX_AGENTS_PER_ROOM   32          /* threads per block */
#define MAX_SCRIPT_RULES      64          /* max rules per script (simplified) */
#define MAX_TURNS_DEFAULT     100
#define MAX_ROOMS_DEFAULT     256
#define MAX_AGENTS_DEFAULT    1024
#define MAX_SCENARIOS_DEFAULT 20

/* -------------------------------------------------------------------------- *
 *  Core data structures (identical for CPU & GPU)
 * -------------------------------------------------------------------------- */
typedef struct {
    int id;
    int room_id;
    int hp;
    int mana;
    int gold;
    int script_id;                 /* which script this avatar runs */
    int inventory[16];
    int flags;                     /* status effects */
} Agent;

typedef struct {
    int id;
    int exits[4];                  /* N,S,E,W room IDs */
    int terrain;                   /* 0=plain … 4=town */
    int items[8];
    int agents_in_room;            /* count of agents present */
} Room;

typedef struct {
    int condition_type;   /* 0=hp_below, 1=enemy_present, 2=item_available, 3=time_elapsed, 4=random */
    int condition_param;
    int action_type;      /* 0=move, 1=attack, 2=pickup, 3=use_item, 4=cast, 5=flee, 6=trade, 7=wait */
    int action_param;
    int priority;         /* lower = higher priority */
} ScriptRule;

typedef struct {
    int health;           /* did agent survive? (1/0) */
    int gold_collected;
    int enemies_defeated;
    int rooms_explored;
    int items_collected;
    int turns_survived;
    int score;            /* composite score */
} ScenarioResult;

/* -------------------------------------------------------------------------- *
 *  Utility helpers
 * -------------------------------------------------------------------------- */
static inline int min_i(int a, int b) { return a < b ? a : b; }

static void init_random_seed(unsigned int *seed) {
    *seed = (unsigned int)time(NULL);
}

/* -------------------------------------------------------------------------- *
 *  GPU kernels
 * -------------------------------------------------------------------------- */
#ifndef NO_CUDA

/* ---------------------------------------------------------------------- *
 *  simulate_scenario
 *  One block = one room, one thread = one avatar in that room.
 * ---------------------------------------------------------------------- */
__global__ void simulate_scenario(Agent *d_agents,
                                  Room  *d_rooms,
                                  ScriptRule *d_scripts,
                                  ScenarioResult *d_results,
                                  int max_turns,
                                  int total_agents)
{
    /* --------------------------------------------------------------
     *  Shared room state (visible to all agents in the block)
     * -------------------------------------------------------------- */
    __shared__ Room s_room;

    int room_id   = blockIdx.x;                     /* block = room */
    int local_tid = threadIdx.x;                    /* thread = avatar in room */
    int global_tid = room_id * MAX_AGENTS_PER_ROOM + local_tid;

    /* --------------------------------------------------------------
     *  Load room into shared memory (once per block)
     * -------------------------------------------------------------- */
    if (local_tid == 0) {
        s_room = d_rooms[room_id];
    }
    __syncthreads();

    /* --------------------------------------------------------------
     *  Early exit if this thread does not map to a real agent
     * -------------------------------------------------------------- */
    if (global_tid >= total_agents) return;
    if (d_agents[global_tid].room_id != room_id) return;

    /* --------------------------------------------------------------
     *  Per‑thread state
     * -------------------------------------------------------------- */
    Agent   agent   = d_agents[global_tid];
    ScenarioResult result;
    memset(&result, 0, sizeof(ScenarioResult));
    result.health = (agent.hp > 0);
    result.turns_survived = 0;

    /* --------------------------------------------------------------
     *  Random generator (simple LCG – deterministic per thread)
     * -------------------------------------------------------------- */
    unsigned int rng = (unsigned int)(global_tid * 1234567 + 891011);

    /* --------------------------------------------------------------
     *  Main simulation loop
     * -------------------------------------------------------------- */
    for (int turn = 0; turn < max_turns; ++turn) {
        if (agent.hp <= 0) break;               /* dead → stop */

        /* ----------------------------------------------------------
         *  Fetch the script rule for this avatar.
         *  For simplicity we assume a single rule per script.
         * ---------------------------------------------------------- */
        ScriptRule rule = d_scripts[agent.script_id];

        /* ----------------------------------------------------------
         *  Evaluate condition (very simplified stub)
         * ---------------------------------------------------------- */
        int condition_met = 0;
        switch (rule.condition_type) {
            case 0: /* hp_below */
                condition_met = (agent.hp < rule.condition_param);
                break;
            case 1: /* enemy_present */
                condition_met = (s_room.agents_in_room > 1);
                break;
            case 2: /* item_available */
                for (int i = 0; i < 8; ++i)
                    if (s_room.items[i] == rule.condition_param) { condition_met = 1; break; }
                break;
            case 3: /* time_elapsed */
                condition_met = (turn >= rule.condition_param);
                break;
            case 4: /* random */
                rng = rng * 1664525u + 1013904223u;
                condition_met = ((rng >> 16) & 0x7FFF) % 100 < rule.condition_param;
                break;
            default:
                condition_met = 1;
        }

        if (!condition_met) continue;   /* no action this turn */

        /* ----------------------------------------------------------
         *  Execute action
         * ---------------------------------------------------------- */
        switch (rule.action_type) {
            case 0: /* move */
                {
                    int dest = rule.action_param % gridDim.x;   /* wrap around world */
                    /* leave current room */
                    atomicSub(&s_room.agents_in_room, 1);
                    __syncthreads();
                    /* update agent */
                    agent.room_id = dest;
                    /* enter destination room (handled by that block in next iteration) */
                }
                break;

            case 1: /* attack */
                {
                    int dmg = 1 + (rng % 7);   /* strength + random(0,6) */
                    agent.hp -= dmg;           /* self‑damage for demo */
                    result.enemies_defeated += 1;
                }
                break;

            case 2: /* pickup */
                {
                    for (int i = 0; i < 8; ++i) {
                        if (s_room.items[i] == rule.action_param) {
                            /* add to first empty inventory slot */
                            for (int j = 0; j < 16; ++j) {
                                if (agent.inventory[j] == 0) {
                                    agent.inventory[j] = s_room.items[i];
                                    s_room.items[i] = 0;
                                    result.items_collected += 1;
                                    break;
                                }
                            }
                            break;
                        }
                    }
                }
                break;

            case 3: /* use_item – stub (no effect) */
                break;

            case 4: /* cast – stub (no effect) */
                break;

            case 5: /* flee – move to a random exit */
                {
                    int exit_idx = rng % 4;
                    int dest = s_room.exits[exit_idx];
                    atomicSub(&s_room.agents_in_room, 1);
                    __syncthreads();
                    agent.room_id = dest;
                }
                break;

            case 6: /* trade – stub */
                break;

            case 7: /* wait – do nothing */
                break;
        }

        result.turns_survived++;
        __syncthreads();   /* ensure room state is consistent */
    }

    /* --------------------------------------------------------------
     *  Write back per‑agent result and final agent state
     * -------------------------------------------------------------- */
    result.health = (agent.hp > 0);
    result.score = result.health * 1000
                 + result.gold_collected * 10
                 + result.enemies_defeated * 20
                 + result.rooms_explored * 5
                 + result.items_collected * 2
                 + result.turns_survived;

    d_results[global_tid] = result;
    d_agents[global_tid]   = agent;          /* write back possible room change */

    /* --------------------------------------------------------------
     *  Write back modified room state (only one thread does it)
     * -------------------------------------------------------------- */
    if (local_tid == 0) {
        d_rooms[room_id] = s_room;
    }
}

/* ---------------------------------------------------------------------- *
 *  evaluate_scripts – simple reduction: average score per script
 * ---------------------------------------------------------------------- */
__global__ void evaluate_scripts(ScenarioResult *d_results,
                                 int *d_script_scores,
                                 int num_agents,
                                 int scenarios_per_script)
{
    int script_id = blockIdx.x * blockDim.x + threadIdx.x;
    if (script_id >= scenarios_per_script) return;   /* one thread per script */

    int sum = 0;
    int count = 0;
    for (int i = 0; i < num_agents; ++i) {
        if (i % scenarios_per_script == script_id) {
            sum   += d_results[i].score;
            count += 1;
        }
    }
    d_script_scores[script_id] = (count > 0) ? (sum / count) : 0;
}
#endif   /* NO_CUDA */

/* -------------------------------------------------------------------------- *
 *  CPU fallback implementations (identical logic, no parallelism)
 * -------------------------------------------------------------------------- */
#ifdef NO_CUDA
static void simulate_scenario_cpu(Agent *agents,
                                  Room  *rooms,
                                  ScriptRule *scripts,
                                  ScenarioResult *results,
                                  int max_turns,
                                  int total_agents)
{
    unsigned int rng;
    for (int gid = 0; gid < total_agents; ++gid) {
        Agent   *agent = &agents[gid];
        Room    *room  = &rooms[agent->room_id];
        ScenarioResult *res = &results[gid];
        memset(res, 0, sizeof(ScenarioResult));
        res->health = (agent->hp > 0);
        rng = (unsigned int)(gid * 1234567 + 891011);

        for (int turn = 0; turn < max_turns; ++turn) {
            if (agent->hp <= 0) break;

            ScriptRule rule = scripts[agent->script_id];
            int condition_met = 0;
            switch (rule.condition_type) {
                case 0: condition_met = (agent->hp < rule.condition_param); break;
                case 1: condition_met = (room->agents_in_room > 1); break;
                case 2:
                    for (int i = 0; i < 8; ++i)
                        if (room->items[i] == rule.condition_param) { condition_met = 1; break; }
                    break;
                case 3: condition_met = (turn >= rule.condition_param); break;
                case 4:
                    rng = rng * 1664525u + 1013904223u;
                    condition_met = ((rng >> 16) & 0x7FFF) % 100 < rule.condition_param;
                    break;
                default: condition_met = 1;
            }
            if (!condition_met) continue;

            switch (rule.action_type) {
                case 0: /* move */
                    {
                        int dest = rule.action_param % (room->id + 1);
                        room->agents_in_room--;
                        agent->room_id = dest;
                        rooms[dest].agents_in_room++;
                    }
                    break;
                case 1: /* attack */
                    {
                        int dmg = 1 + (rng % 7);
                        agent->hp -= dmg;
                        res->enemies_defeated++;
                    }
                    break;
                case 2: /* pickup */
                    {
                        for (int i = 0; i < 8; ++i) {
                            if (room->items[i] == rule.action_param) {
                                for (int j = 0; j < 16; ++j) {
                                    if (agent->inventory[j] == 0) {
                                        agent->inventory[j] = room->items[i];
                                        room->items[i] = 0;
                                        res->items_collected++;
                                        break;
                                    }
                                }
                                break;
                            }
                        }
                    }
                    break;
                case 5: /* flee */
                    {
                        int exit_idx = rng % 4;
                        int dest = room->exits[exit_idx];
                        room->agents_in_room--;
                        agent->room_id = dest;
                        rooms[dest].agents_in_room++;
                    }
                    break;
                default: break;
            }
            res->turns_survived++;
        }
        res->health = (agent->hp > 0);
        res->score = res->health * 1000
                   + res->gold_collected * 10
                   + res->enemies_defeated * 20
                   + res->rooms_explored * 5
                   + res->items_collected * 2
                   + res->turns_survived;
    }
}

static void evaluate_scripts_cpu(ScenarioResult *results,
                                 int *script_scores,
                                 int num_agents,
                                 int scenarios_per_script)
{
    for (int sid = 0; sid < scenarios_per_script; ++sid) {
        int sum = 0, cnt = 0;
        for (int i = 0; i < num_agents; ++i) {
            if (i % scenarios_per_script == sid) {
                sum += results[i].score;
                cnt++;
            }
        }
        script_scores[sid] = (cnt > 0) ? (sum / cnt) : 0;
    }
}
#endif   /* NO_CUDA */

/* -------------------------------------------------------------------------- *
 *  Command line parsing helpers
 * -------------------------------------------------------------------------- */
static void print_usage(const char *prog) {
    printf("Usage: %s [--agents N] [--rooms N] [--turns N] [--scenarios N]\n", prog);
}

/* -------------------------------------------------------------------------- *
 *  Main entry point
 * -------------------------------------------------------------------------- */
int main(int argc, char **argv)
{
    int num_agents    = MAX_AGENTS_DEFAULT;
    int num_rooms     = MAX_ROOMS_DEFAULT;
    int max_turns     = MAX_TURNS_DEFAULT;
    int scenarios_per_script = MAX_SCENARIOS_DEFAULT;

    /* ---- parse arguments ------------------------------------------------- */
    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--agents") == 0 && i + 1 < argc) {
            num_agents = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--rooms") == 0 && i + 1 < argc) {
            num_rooms = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--turns") == 0 && i + 1 < argc) {
            max_turns = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--scenarios") == 0 && i + 1 < argc) {
            scenarios_per_script = atoi(argv[++i]);
        } else {
            print_usage(argv[0]);
            return 1;
        }
    }

    /* ---- allocate host data --------------------------------------------- */
    Agent          *h_agents   = (Agent*)malloc(num_agents * sizeof(Agent));
    Room           *h_rooms    = (Room*)malloc(num_rooms  * sizeof(Room));
    ScriptRule     *h_scripts  = (ScriptRule*)malloc(num_rooms * sizeof(ScriptRule)); /* one script per room for demo */
    ScenarioResult *h_results  = (ScenarioResult*)malloc(num_agents * sizeof(ScenarioResult));
    int            *h_script_scores = (int*)malloc(num_rooms * sizeof(int));

    /* ---- initialise random seed ------------------------------------------ */
    srand((unsigned)time(NULL));

    /* ---- initialise agents ----------------------------------------------- */
    for (int i = 0; i < num_agents; ++i) {
        h_agents[i].id        = i;
        h_agents[i].room_id   = i % num_rooms;
        h_agents[i].hp        = 100;
        h_agents[i].mana      = 100;
        h_agents[i].gold      = 0;
        h_agents[i].script_id = h_agents[i].room_id;   /* each room has its own script */
        memset(h_agents[i].inventory, 0, sizeof(h_agents[i].inventory));
        h_agents[i].flags     = 0;
    }

    /* ---- initialise rooms ------------------------------------------------ */
    for (int i = 0; i < num_rooms; ++i) {
        h_rooms[i].id = i;
        h_rooms[i].exits[0] = (i + 1) % num_rooms;                     /* N */
        h_rooms[i].exits[1] = (i - 1 + num_rooms) % num_rooms;        /* S */
        h_rooms[i].exits[2] = (i + num_rooms/2) % num_rooms;          /* E */
        h_rooms[i].exits[3] = (i - num_rooms/2 + num_rooms) % num_rooms;/* W */
        h_rooms[i].terrain = i % 5;
        for (int j = 0; j < 8; ++j) h_rooms[i].items[j] = (rand()%20);
        h_rooms[i].agents_in_room = 0;
    }
    /* count agents per room */
    for (int i = 0; i < num_agents; ++i) {
        int rid = h_agents[i].room_id;
        if (rid >= 0 && rid < num_rooms) h_rooms[rid].agents_in_room++;
    }

    /* ---- initialise scripts (one per room) ------------------------------ */
    for (int i = 0; i < num_rooms; ++i) {
        h_scripts[i].condition_type = rand() % 5;
        h_scripts[i].condition_param = rand() % 100;
        h_scripts[i].action_type = rand() % 8;
        h_scripts[i].action_param = rand() % num_rooms;
        h_scripts[i].priority = i;
    }

#ifndef NO_CUDA
    /* ------------------------------------------------------------------ *
     *  GPU execution
     * ------------------------------------------------------------------ */
    Agent        *d_agents   = NULL;
    Room         *d_rooms    = NULL;
    ScriptRule   *d_scripts  = NULL;
    ScenarioResult *d_results = NULL;
    int          *d_script_scores = NULL;

    cudaMalloc((void**)&d_agents,   num_agents * sizeof(Agent));
    cudaMalloc((void**)&d_rooms,    num_rooms  * sizeof(Room));
    cudaMalloc((void**)&d_scripts,  num_rooms  * sizeof(ScriptRule));
    cudaMalloc((void**)&d_results,  num_agents * sizeof(ScenarioResult));
    cudaMalloc((void**)&d_script_scores, num_rooms * sizeof(int));

    cudaMemcpy(d_agents,   h_agents,  num_agents * sizeof(Agent),   cudaMemcpyHostToDevice);
    cudaMemcpy(d_rooms,    h_rooms,   num_rooms  * sizeof(Room),    cudaMemcpyHostToDevice);
    cudaMemcpy(d_scripts,  h_scripts, num_rooms  * sizeof(ScriptRule), cudaMemcpyHostToDevice);

    /* ---- launch simulation kernel ------------------------------------ */
    dim3 grid(num_rooms);
    dim3 block(min_i(MAX_AGENTS_PER_ROOM, 32));
    simulate_scenario<<<grid, block>>>(d_agents,
                                       d_rooms,
                                       d_scripts,
                                       d_results,
                                       max_turns,
                                       num_agents);
    cudaDeviceSynchronize();

    /* ---- copy back results -------------------------------------------- */
    cudaMemcpy(h_results, d_results, num_agents * sizeof(ScenarioResult), cudaMemcpyDeviceToHost);
    cudaMemcpy(h_rooms,   d_rooms,   num_rooms  * sizeof(Room),          cudaMemcpyDeviceToHost);

    /* ---- evaluate scripts --------------------------------------------- */
    dim3 eval_grid( (num_rooms + 31) / 32 );
    dim3 eval_block(32);
    evaluate_scripts<<<eval_grid, eval_block>>>(d_results,
                                                d_script_scores,
                                                num_agents,
                                                scenarios_per_script);
    cudaDeviceSynchronize();
    cudaMemcpy(h_script_scores, d_script_scores, num_rooms * sizeof(int), cudaMemcpyDeviceToHost);

    /* ---- cleanup ------------------------------------------------------ */
    cudaFree(d_agents);
    cudaFree(d_rooms);
    cudaFree(d_scripts);
    cudaFree(d_results);
    cudaFree(d_script_scores);
#else
    /* ------------------------------------------------------------------ *
     *  CPU execution (fallback)
     * ------------------------------------------------------------------ */
    clock_t t_start = clock();
    simulate_scenario_cpu(h_agents, h_rooms, h_scripts, h_results,
                          max_turns, num_agents);
    evaluate_scripts_cpu(h_results, h_script_scores,
                         num_agents, scenarios_per_script);
    clock_t t_end = clock();
    double cpu_time = (double)(t_end - t_start) / CLOCKS_PER_SEC;
    printf("[CPU] Simulation + evaluation time: %.3f s\n", cpu_time);
#endif

    /* ---- output script rankings ---------------------------------------- */
    printf("\n=== Script Rankings (higher score = better) ===\n");
    for (int i = 0; i < num_rooms; ++i) {
        printf("Script %3d : average score = %d\n", i, h_script_scores[i]);
    }

    /* ---- free host memory ---------------------------------------------- */
    free(h_agents);
    free(h_rooms);
    free(h_scripts);
    free(h_results);
    free(h_script_scores);

    return 0;
}
```