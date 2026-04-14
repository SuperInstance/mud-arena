```c
/* src/wasm_mud.c */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <emscripten/emscripten.h>

#pragma pack(push,1)
typedef struct {
    int   id;
    char  name[32];
    char  description[128];
    int   exits[4];          /* 0:N 1:E 2:S 3:W, -1 = none */
    int   terrain;
    int   items[8];
    int   num_agents;
} Room;

typedef struct {
    int   id;
    char  name[16];
    int   room_id;
    int   hp;
    int   battery;
    int   script_id;
    int   state;
    char  task[64];
} Agent;

typedef struct {
    int   id;
    int   room_id;
    int   perception_mode;
    int   battery_aware;
} HumanAvatar;

typedef struct {
    Room          rooms[64];
    Agent         agents[32];
    HumanAvatar   human;
    int           turn;
    int           comm_resolution;   /* 0‑100 % */
} WorldState;
#pragma pack(pop)

static WorldState world;
static char last_output[1024];
static char room_json[256];
static char agents_json[2048];
static char calibration_vars[16][32];
static int  calibration_vals[16];
static int  calibration_cnt = 0;

/* -------------------------------------------------------------------------- */
static void append_output(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(last_output + strlen(last_output), sizeof(last_output) - strlen(last_output), fmt, ap);
    va_end(ap);
}

/* -------------------------------------------------------------------------- */
static int find_agent_by_name(const char *name) {
    for (int i = 0; i < 32; ++i) {
        if (world.agents[i].id >= 0 && strcmp(world.agents[i].name, name) == 0)
            return i;
    }
    return -1;
}

/* -------------------------------------------------------------------------- */
static int distance_from_dock(int room_id) {
    /* simple BFS distance (max 10 rooms) */
    static int dist[64];
    static int q[64];
    static int visited[64];
    memset(dist, -1, sizeof(dist));
    memset(visited, 0, sizeof(visited));
    int head = 0, tail = 0;
    q[tail++] = 0;               /* dock is room 0 */
    dist[0] = 0;
    visited[0] = 1;
    while (head < tail) {
        int cur = q[head++];
        if (cur == room_id) break;
        for (int d = 0; d < 4; ++d) {
            int nxt = world.rooms[cur].exits[d];
            if (nxt >= 0 && !visited[nxt]) {
                visited[nxt] = 1;
                dist[nxt] = dist[cur] + 1;
                q[tail++] = nxt;
            }
        }
    }
    return (room_id >= 0 && dist[room_id] >= 0) ? dist[room_id] : 10;
}

/* -------------------------------------------------------------------------- */
static void update_comm_resolution(void) {
    int d = distance_from_dock(world.human.room_id);
    world.comm_resolution = (d >= 10) ? 0 : 100 - d * 10;
}

/* -------------------------------------------------------------------------- */
EMSCRIPTEN_KEEPALIVE
void mud_init(void) {
    memset(&world, 0, sizeof(world));
    world.turn = 0;
    world.comm_resolution = 100;

    /* ----- rooms ----- */
    const char *room_names[10] = {
        "dock","bridge","engine_room","cargo_bay","sensor_deck",
        "forest_1","forest_2","forest_3","forest_4","forest_5"
    };
    const char *room_descs[10] = {
        "You stand on the docking platform of the ship.",
        "The bridge is filled with consoles and a large viewport.",
        "The engine room hums with power.",
        "Stacks of crates fill the cargo bay.",
        "Sensors blink on the deck above the ship.",
        "Tall trees surround you, the forest floor is soft.",
        "The canopy thickens, shadows dance.",
        "A clearing opens, sunlight streams down.",
        "A narrow path winds through dense foliage.",
        "The forest thins, the edge of the unknown looms."
    };
    for (int i = 0; i < 10; ++i) {
        Room *r = &world.rooms[i];
        r->id = i;
        strncpy(r->name, room_names[i], sizeof(r->name));
        strncpy(r->description, room_descs[i], sizeof(r->description));
        for (int d = 0; d < 4; ++d) r->exits[d] = -1;
        r->terrain = (i >= 5) ? 1 : 0;   /* 0 = ship, 1 = forest */
    }
    /* simple linear connections */
    world.rooms[0].exits[1] = 1;   /* dock -> bridge (east) */
    world.rooms[1].exits[2] = 2;   /* bridge -> engine_room (south) */
    world.rooms[2].exits[3] = 3;   /* engine_room -> cargo_bay (west) */
    world.rooms[3].exits[0] = 4;   /* cargo_bay -> sensor_deck (north) */
    world.rooms[4].exits[1] = 5;   /* sensor_deck -> forest_1 (east) */
    world.rooms[5].exits[1] = 6;
    world.rooms[6].exits[1] = 7;
    world.rooms[7].exits[1] = 8;
    world.rooms[8].exits[1] = 9;

    /* ----- agents ----- */
    const char *agent_names[3] = {"pilot","sensor_op","surveyor"};
    int agent_rooms[3] = {0,1,2};
    for (int i = 0; i < 3; ++i) {
        Agent *a = &world.agents[i];
        a->id = i;
        strncpy(a->name, agent_names[i], sizeof(a->name));
        a->room_id = agent_rooms[i];
        a->hp = 100;
        a->battery = 100;
        a->script_id = i;   /* dummy script id */
        a->state = 0;
        a->task[0] = '\0';
    }

    /* ----- human ----- */
    world.human.id = 0;
    world.human.room_id = 0;          /* starts at dock */
    world.human.perception_mode = 0;
    world.human.battery_aware = 100;

    last_output[0] = '\0';
}

/* -------------------------------------------------------------------------- */
EMSCRIPTEN_KEEPALIVE
int mud_command(const char *cmd_ptr) {
    char cmd[256];
    strncpy(cmd, cmd_ptr, sizeof(cmd)-1);
    cmd[255] = '\0';
    last_output[0] = '\0';

    if (strncmp(cmd, "brief ", 6) == 0) {
        char agent_name[32];
        char mission[64];
        if (sscanf(cmd+6, "%31s %63[^\n]", agent_name, mission) == 2) {
            int idx = find_agent_by_name(agent_name);
            if (idx >= 0) {
                strncpy(world.agents[idx].task, mission, sizeof(world.agents[idx].task));
                append_output("Agent %s briefed: %s\n", agent_name, mission);
            } else {
                append_output("No such agent: %s\n", agent_name);
            }
        }
    } else if (strcmp(cmd, "battery") == 0) {
        append_output("Human battery awareness: %d%%\n", world.human.battery_aware);
    } else if (strcmp(cmd, "comm") == 0) {
        update_comm_resolution();
        append_output("Comm resolution: %d%%\n", world.comm_resolution);
    } else if (strcmp(cmd, "beam off") == 0) {
        world.human.room_id = -1;
        append_output("Human has beamed off.\n");
    } else if (strncmp(cmd, "measure ", 8) == 0) {
        char var[32];
        int val;
        if (sscanf(cmd+8, "%31s %d", var, &val) == 2) {
            if (calibration_cnt < 16) {
                strncpy(calibration_vars[calibration_cnt], var, 32);
                calibration_vals[calibration_cnt] = val;
                ++calibration_cnt;
                append_output("Calibration recorded: %s = %d\n", var, val);
            } else {
                append_output("Calibration storage full.\n");
            }
        }
    } else {
        append_output("Unknown command.\n");
    }
    return (int)strlen(last_output);
}

/* -------------------------------------------------------------------------- */
EMSCRIPTEN_KEEPALIVE
void mud_tick(void) {
    ++world.turn;
    for (int i = 0; i < 32; ++i) {
        Agent *a = &world.agents[i];
        if (a->id < 0) continue;
        if (a->battery > 0) {
            a->battery -= 1;                     /* simple consumption */
            if (a->battery == 0) a->state = 1;   /* 1 = out of power */
        }
        /* simple autonomous movement when comm is 0 */
        if (world.comm_resolution == 0 && a->battery > 0) {
            int cur = a->room_id;
            for (int d = 0; d < 4; ++d) {
                int nxt = world.rooms[cur].exits[d];
                if (nxt >= 0) { a->room_id = nxt; break; }
            }
        }
    }
    if (world.human.room_id >= 0 && world.human.battery_aware > 0) {
        world.human.battery_aware -= 1;
    }
    update_comm_resolution();
}

/* -------------------------------------------------------------------------- */
EMSCRIPTEN_KEEPALIVE
const char* mud_get_output(void) {
    return last_output;
}

/* -------------------------------------------------------------------------- */
EMSCRIPTEN_KEEPALIVE
const char* mud_get_room(int room_id) {
    if (room_id < 0 || room_id >= 64) return "{}";
    Room *r = &world.rooms[room_id];
    snprintf(room_json, sizeof(room_json),
        "{\"id\":%d,\"name\":\"%s\",\"description\":\"%s\",\"exits\":[%d,%d,%d,%d],\"terrain\":%d}",
        r->id, r->name, r->description,
        r->exits[0], r->exits[1], r->exits[2], r->exits[3],
        r->terrain);
    return room_json;
}

/* -------------------------------------------------------------------------- */
EMSCRIPTEN_KEEPALIVE
const char* mud_get_agents(void) {
    char *p = agents_json;
    p[0] = '['; p[1] = '\0';
    int first = 1;
    for (int i = 0; i < 32; ++i) {
        Agent *a = &world.agents[i];
        if (a->id < 0) continue;
        if (!first) strcat(p, ",");
        first = 0;
        char buf[256];
        snprintf(buf, sizeof(buf),
            "{\"id\":%d,\"name\":\"%s\",\"room_id\":%d,\"hp\":%d,\"battery\":%d,\"task\":\"%s\"}",
            a->id, a->name, a->room_id, a->hp, a->battery, a->task);
        strcat(p, buf);
    }
    strcat(p, "]");
    return agents_json;
}

/* -------------------------------------------------------------------------- */
EMSCRIPTEN_KEEPALIVE
void mud_human_enter(const char *name_ptr) {
    (void)name_ptr;                     /* name not stored in struct */
    world.human.room_id = 0;            /* dock */
    world.human.perception_mode = 0;
    world.human.battery_aware = 100;
    append_output("Human entered the ship at dock.\n");
}

/* -------------------------------------------------------------------------- */
EMSCRIPTEN_KEEPALIVE
int mud_human_act(const char *cmd_ptr) {
    char cmd[256];
    strncpy(cmd, cmd_ptr, sizeof(cmd)-1);
    cmd[255] = '\0';
    last_output[0] = '\0';

    if (strcmp(cmd, "look") == 0) {
        if (world.human.room_id >= 0) {
            Room *r = &world.rooms[world.human.room_id];
            append_output("%s\n", r->description);
        } else {
            append_output("You are not on board.\n");
        }
    } else if (strncmp(cmd, "move ", 5) == 0) {
        char dir[8];
        if (sscanf(cmd+5, "%7s", dir) == 1) {
            int d = -1;
            if (strcmp(dir, "north")==0) d=0;
            else if (strcmp(dir, "east")==0) d=1;
            else if (strcmp(dir, "south")==0) d=2;
            else if (strcmp(dir, "west")==0) d=3;
            if (d>=0 && world.human.room_id>=0) {
                int nxt = world.rooms[world.human.room_id].exits[d];
                if (nxt>=0) {
                    world.human.room_id = nxt;
                    append_output("Moved %s to %s.\n", dir, world.rooms[nxt].name);
                } else {
                    append_output("No exit %s.\n", dir);
                }
            }
        }
    } else if (strncmp(cmd, "talk ",5)==0) {
        char agent_name[32];
        if (sscanf(cmd+5, "%31s", agent_name)==1) {
            int idx = find_agent_by_name(agent_name);
            if (idx>=0 && world.agents[idx].room_id==world.human.room_id) {
                append_output("You talk to %s. Their task: %s\n", agent_name, world.agents[idx].task);
            } else {
                append_output("Agent %s not present.\n", agent_name);
            }
        }
    } else if (strncmp(cmd, "brief ",6)==0) {
        char agent_name[32];
        char mission[64];
        if (sscanf(cmd+6, "%31s %63[^\n]", agent_name, mission)==2) {
            int idx = find_agent_by_name(agent_name);
            if (idx>=0) {
                strncpy(world.agents[idx].task, mission, sizeof(world.agents[idx].task));
                append_output("Briefed %s: %s\n", agent_name, mission);
            } else {
                append_output("No such agent.\n");
            }
        }
    } else if (strncmp(cmd, "measure ",8)==0) {
        char var[32];
        int val;
        if (sscanf(cmd+8, "%31s %d", var, &val)==2) {
            mud_measure(var, val);
            append_output("Measured %s = %d\n", var, val);
        }
    } else {
        append_output("Unknown human action.\n");
    }
    return (int)strlen(last_output);
}

/* -------------------------------------------------------------------------- */
EMSCRIPTEN_KEEPALIVE
void mud_measure(const char *var_ptr, int actual_value) {
    if (calibration_cnt < 16) {
        strncpy(calibration_vars[calibration_cnt], var_ptr, 32);
        calibration_vals[calibration_cnt] = actual_value;
        ++calibration_cnt;
    }
}
```