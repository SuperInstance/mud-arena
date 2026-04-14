```c
#ifndef HUMAN_AVATAR_H
#define HUMAN_AVATAR_H

/*--------------------------------------------------------------------
 *  CUDA‑compatible header for human avatars in a MUD simulation
 *--------------------------------------------------------------------*/

#include <stdbool.h>
#include <stddef.h>

/*---------------------------  Enums  --------------------------------*/

typedef enum {
    PERCEPTION_NORMAL,
    PERCEPTION_CALIBRATION,
    PERCEPTION_AGENT_VIEW,
    PERCEPTION_GOD
} PerceptionMode;

/*--------------------------  Types  --------------------------------*/

typedef struct Agent Agent;   /* Forward declaration – defined elsewhere */

/* Calibration point – one entry in the calibration log */
typedef struct {
    char   variable_name[64];
    float  predicted;
    float  actual;
    float  timestamp;
    char   unit[32];
    char   source[64];
} CalibrationPoint;

/* Buffer returned by human_perceive() */
typedef struct {
    char   room_description[512];
    char   exits[4][32];                 /* e.g. "north", "south", … */
    Agent* visible_agents[16];
    Agent* visible_items[16];
    float* exact_values;                /* Used only in CALIBRATION mode */
} PerceptionBuffer;

/* Human avatar – extends Agent */
typedef struct {
    Agent          base;                 /* Inheritance (must be first) */
    bool           human_controlled;
    PerceptionMode perception_mode;
    /* Circular command queue – 16 slots, each command up to 64 chars */
    char           action_queue[16][64];
    int            queue_head;           /* Index of next command to read */
    int            queue_tail;           /* Index of next free slot      */
    CalibrationPoint* calibration_data; /* Optional pointer to log data */
} HumanAvatar;

/*--------------------------  Prototypes  -----------------------------*/

/* Creation */
__host__ __device__
HumanAvatar* human_avatar_create(int id, int room_id);

/* Perception – fills a PerceptionBuffer according to avatar->perception_mode */
__host__ __device__
PerceptionBuffer human_perceive(const HumanAvatar* avatar, const void* room);

/* Process a human command; returns 0 on success, non‑zero error code */
__host__ __device__
int human_act(HumanAvatar* avatar, const char* command);

/* Calibration utilities */
__host__ __device__
CalibrationPoint calibration_record(const char* variable,
                                    float predicted,
                                    float actual,
                                    const char* unit,
                                    const char* source);

__host__ __device__
float calibration_get_tolerance(const char* variable);

__host__ __device__
int calibration_is_drifting(const char* variable);

#endif /* HUMAN_AVATAR_H */
```