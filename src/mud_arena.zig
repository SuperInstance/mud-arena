```zig
//! MUD‑Arena edge runtime – a single‑file Zig implementation.
//! Targets: aarch64‑linux (Raspberry Pi, Jetson), x86_64‑linux, wasm32‑wasi.
//! Compiles to a tiny static binary (< 100 KB with -O ReleaseSmall).
//! No external libraries – only Zig stdlib.

const std = @import("std");
const builtin = @import("builtin");

//===================================================================
//  Data structures
//===================================================================

pub const Terrain = enum {
    dock,
    bridge,
    engine,
    cargo,
    sensor,
    forest,
    clearing,
    water,
    base,
};

pub const ItemKind = enum {
    tool,
    sample,
    data,
    battery,
    sensor,
};

pub const Item = struct {
    id: u8,
    name: [32]u8,
    kind: ItemKind,
};

pub const Room = struct {
    id: u8,
    name: [32]u8,
    desc: [128]u8,
    // exits: N,E,S,W → room id or 0xFF for none
    exits: [4]u8,
    terrain: Terrain,
    items: [8]?Item,
};

pub const Condition = union(enum) {
    hp_below: u16,
    battery_below: u16,
    enemy_present: void,
    item_available: void,
    time_elapsed: u32,
    comm_lost: void,
    has_task: void,
    cargo_full: void,
    random: u8, // N % chance
};

pub const Action = union(enum) {
    move: u8, // target room id
    attack: void,
    pickup: void,
    use_item: u8,
    flee: void,
    return_base: void,
    report: void,
    wait: u32, // ticks
    autonomous: void,
};

pub const ScriptRule = struct {
    condition: Condition,
    action: Action,
    priority: u8,
};

pub const AgentState = enum {
    idle,
    exploring,
    collecting,
    returning,
    low_battery,
    comms_lost,
    autonomous,
};

pub const Agent = struct {
    id: u8,
    name: [16]u8,
    room: u8,
    hp: u16,
    battery: u16, // 0‑1000 (milli‑percent)
    script: []const ScriptRule,
    state: AgentState,
    task: [64]u8, // mission briefing (utf‑8, null‑terminated)
    cargo: [8]?Item,
};

pub const PerceptionMode = enum {
    normal,
    calibration,
    agent_view,
    god,
};

pub const HumanAvatar = struct {
    present: bool,
    room: u8,
    mode: PerceptionMode,
    comm_resolution: u8, // 0‑100 %
};

pub const WorldStatus = struct {
    tick: u32,
    human_present: bool,
    human_room: u8,
    comm_resolution: u8,
    agents_active: u8,
};

//===================================================================
//  World implementation
//===================================================================

pub const World = struct {
    rooms: [64]Room,
    agents: [32]Agent,
    human: HumanAvatar,
    tick: u32,
    base_room: u8,

    // ----------------------------------------------------------------
    //  Initialise a tiny demo world (2 rooms, 1 agent)
    // ----------------------------------------------------------------
    pub fn init() World {
        var world = World{
            .rooms = undefined,
            .agents = undefined,
            .human = .{
                .present = false,
                .room = 0,
                .mode = .normal,
                .comm_resolution = 100,
            },
            .tick = 0,
            .base_room = 0,
        };

        // ---- rooms ----------------------------------------------------
        // room 0 – Dock (the “ship”)
        world.rooms[0] = Room{
            .id = 0,
            .name = "Dock".*,
            .desc = "You stand on the docking platform of the ship. A hatch leads north."
                .*,
            .exits = .{ 1, 0xFF, 0xFF, 0xFF }, // N,E,S,W
            .terrain = .dock,
            .items = .{null} ** 8,
        };
        // room 1 – Bridge (inside the ship)
        world.rooms[1] = Room{
            .id = 1,
            .name = "Bridge".*,
            .desc = "The bridge is filled with consoles and a large viewport."
                .*,
            .exits = .{ 0xFF, 0xFF, 0xFF, 0 }, // N,E,S,W (west back to dock)
            .terrain = .bridge,
            .items = .{null} ** 8,
        };

        // ---- a single agent -------------------------------------------
        const dummy_script: []const ScriptRule = &[_]ScriptRule{};
        world.agents[0] = Agent{
            .id = 0,
            .name = "Scout".*,
            .room = 1,
            .hp = 1000,
            .battery = 1000,
            .script = dummy_script,
            .state = .idle,
            .task = [_]u8{0} ** 64,
            .cargo = .{null} ** 8,
        };

        // ---- human avatar ---------------------------------------------
        world.human = HumanAvatar{
            .present = false,
            .room = 0,
            .mode = .normal,
            .comm_resolution = 100,
        };

        return world;
    }

    // ----------------------------------------------------------------
    //  One tick (called every 100 ms). Handles battery drain,
    //  autonomous state changes and communication decay.
    // ----------------------------------------------------------------
    pub fn tick(self: *World) void {
        self.tick +%= 1;

        // Simple battery drain for every agent
        for (self.agents) |*agent| {
            if (agent.battery > 0) {
                agent.battery -%= 1; // 0.1 % per tick
            }
            // Low‑battery handling
            if (agent.battery < 200 and agent.state != .low_battery) {
                agent.state = .low_battery;
            }
        }

        // Update human‑to‑agent communication resolution
        self.update_comm_resolution();
    }

    // ----------------------------------------------------------------
    //  Update human.comm_resolution based on distance to the nearest
    //  active agent and on the human's battery (if any).  Very simple.
    // ----------------------------------------------------------------
    pub fn update_comm_resolution(self: *World) void {
        var best: u8 = 100;
        for (self.agents) |agent| {
            if (agent.state == .idle or agent.state == .autonomous) continue;
            const d = if (agent.room > self.human.room)
                agent.room - self.human.room
            else
                self.human.room - agent.room;
            const loss = @intCast(u8, d * 20); // 20 % per room distance
            if (loss < best) best = loss;
        }
        self.human.comm_resolution = if (best > 100) 0 else 100 - best;
    }

    // ----------------------------------------------------------------
    //  Process a command entered by the human avatar.
    //  Returns a static string slice (valid for the lifetime of the
    //  program).  For a real server you would allocate a buffer.
    // ----------------------------------------------------------------
    pub fn process_command(self: *World, cmd: []const u8) []const u8 {
        const trimmed = std.mem.trim(u8, cmd, " \r\n");
        if (trimmed.len == 0) return "??";

        // split first word
        var it = std.mem.split(u8, trimmed, " ");
        const verb = it.next() orelse "";
        const arg = it.next() orelse "";

        switch (verb) {
            "look" => {
                var buf: [512]u8 = undefined;
                const out = format_room(self, self.human.room, self.human.mode, &buf);
                return out;
            },
            "go" => {
                const dir = std.ascii.toLower(arg);
                const dir_idx = switch (dir) {
                    "n" => 0,
                    "e" => 1,
                    "s" => 2,
                    "w" => 3,
                    else => return "unknown direction (use n/e/s/w)",
                };
                const cur = &self.rooms[self.human.room];
                const target = cur.exits[dir_idx];
                if (target == 0xFF) return "no exit that way";
                self.human.room = target;
                return "you move.";
            },
            "status" => {
                var buf: [256]u8 = undefined;
                const out = format_status(self, &buf);
                return out;
            },
            "agents" => {
                var buf: [256]u8 = undefined;
                var writer = std.io.fixedBufferStream(&buf).writer();
                try writer.print("Agents:\n", .{});
                for (self.agents) |agent| {
                    if (agent.name[0] == 0) continue;
                    try writer.print("  {s} (room {d}) battery {d}% state {s}\n",
                        .{
                            std.mem.sliceTo(&agent.name, 0),
                            agent.room,
                            agent.battery / 10,
                            @tagName(agent.state),
                        });
                }
                return std.mem.sliceTo(&buf, 0);
            },
            "brief" => {
                // usage: brief <agent_id> <text>
                const id_str = arg;
                const rest = it.rest();
                const id = std.fmt.parseInt(u8, id_str, 10) catch return "bad agent id";
                if (id >= self.agents.len) return "no such agent";
                self.brief_agent(id, rest);
                return "mission uploaded";
            },
            "quit", "exit" => {
                self.human_leave();
                std.process.exit(0);
            },
            else => return "unknown command",
        }
    }

    // ----------------------------------------------------------------
    //  Human enters the world (e.g. after a network connection)
    // ----------------------------------------------------------------
    pub fn human_enter(self: *World) []const u8 {
        self.human.present = true;
        self.human.room = self.base_room;
        return "Welcome to MUD‑Arena! Type 'look' to see your surroundings.";
    }

    // ----------------------------------------------------------------
    //  Human leaves – agents keep running autonomously
    // ----------------------------------------------------------------
    pub fn human_leave(self: *World) []const u8 {
        self.human.present = false;
        return "You disconnect. Agents continue on their own.";
    }

    // ----------------------------------------------------------------
    //  Human performs an action (currently just forwards to
    //  process_command).  Kept for API compatibility.
    // ----------------------------------------------------------------
    pub fn human_act(self: *World, cmd: []const u8) []const u8 {
        return self.process_command(cmd);
    }

    // ----------------------------------------------------------------
    //  Store a mission briefing into the agent's task buffer.
    // ----------------------------------------------------------------
    pub fn brief_agent(self: *World, agent_id: u8, mission: []const u8) void {
        if (agent_id >= self.agents.len) return;
        const agent = &self.agents[agent_id];
        const limit = @min(mission.len, agent.task.len - 1);
        std.mem.copy(u8, &agent.task, mission[0..limit]);
        agent.task[limit] = 0; // NUL‑terminate
        agent.state = .autonomous;
    }

    // ----------------------------------------------------------------
    //  Return a snapshot of world status.
    // ----------------------------------------------------------------
    pub fn get_status(self: *World) WorldStatus {
        var active: u8 = 0;
        for (self.agents) |a| {
            if (a.state != .idle) active += 1;
        }
        return WorldStatus{
            .tick = self.tick,
            .human_present = self.human.present,
            .human_room = self.human.room,
            .comm_resolution = self.human.comm_resolution,
            .agents_active = active,
        };
    }

    // ----------------------------------------------------------------
    //  Format a room description according to the requested perception
    //  mode.  Returns a slice into the supplied buffer.
    // ----------------------------------------------------------------
    pub fn format_room(world: *World, room_id: u8, mode: PerceptionMode, buf: []u8) []const u8 {
        const room = &world.rooms[room_id];
        var stream = std.io.fixedBufferStream(buf);
        const w = stream.writer();

        // Basic description (always shown)
        _ = w.print("{s}\n{s}\n", .{
            std.mem.sliceTo(&room.name, 0),
            std.mem.sliceTo(&room.desc, 0),
        }) catch {};

        // Exits (only in normal/god mode)
        if (mode == .normal or mode == .god) {
            const dirs = [_][]const u8{ "north", "east", "south", "west" };
            var any = false;
            for (room.exits) |e, i| {
                if (e != 0xFF) {
                    any = true;
                    _ = w.print("  {s} leads to room {d}\n", .{ dirs[i], e }) catch {};
                }
            }
            if (!any) _ = w.print("  No visible exits.\n", .{}) catch {};
        }

        // Items (only in god or calibration mode)
        if (mode == .god or mode == .calibration) {
            var found = false;
            for (room.items) |opt| {
                if (opt) |it| {
                    found = true;
                    _ = w.print("  You see a {s} here.\n", .{
                        std.mem.sliceTo(&it.name, 0),
                    }) catch {};
                }
            }
            if (!found) _ = w.print("  Nothing of interest.\n", .{}) catch {};
        }

        return std.mem.sliceTo(buf, 0);
    }

    // ----------------------------------------------------------------
    //  Format a short world status line.
    // ----------------------------------------------------------------
    pub fn format_status(world: *World, buf: []u8) []const u8 {
        var stream = std.io.fixedBufferStream(buf);
        const w = stream.writer();
        const st = world.get_status();
        _ = w.print(
            "tick {d} | human {s} (room {d}) | comm {d}% | active agents {d}\n",
            .{
                st.tick,
                if (st.human_present) "present" else "absent",
                st.human_room,
                st.comm_resolution,
                st.agents_active,
            },
        ) catch {};
        return std.mem.sliceTo(buf, 0);
    }

    // ----------------------------------------------------------------
    //  Format a view of a single agent (used for debugging / god mode)
    // ----------------------------------------------------------------
    pub fn format_agent_view(world: *World, agent_id: u8, buf: []u8) []const u8 {
        if (agent_id >= world.agents.len) return "no such agent";
        const a = &world.agents[agent_id];
        var stream = std.io.fixedBufferStream(buf);
        const w = stream.writer();
        _ = w.print(
            "Agent {d} – {s}\n  room {d}\n  hp {d}\n  battery {d}%\n  state {s}\n",
            .{
                a.id,
                std.mem.sliceTo(&a.name, 0),
                a.room,
                a.hp,
                a.battery / 10,
                @tagName(a.state),
            },
        ) catch {};
        if (a.task[0] != 0) {
            _ = w.print("  task: {s}\n", .{std.mem.sliceTo(&a.task, 0)}) catch {};
        }
        return std.mem.sliceTo(buf, 0);
    }
};

//===================================================================
//  Helper: simple thread that calls World.tick() every 100 ms
//===================================================================

fn tick_thread(arg: *World) void {
    const period = std.time.ns_per_ms * 100; // 100 ms
    while (true) {
        std.time.sleep(period);
        arg.tick();
    }
}

//===================================================================
//  Main – terminal interface (stdin/stdout)
//===================================================================

pub fn main() !void {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const allocator = arena.allocator();

    var world = World.init();

    // Spawn background ticking thread
    const tick_handle = try std.Thread.spawn(.{}, tick_thread, &world);
    defer tick_handle.join();

    // Greet the user
    std.debug.print("{s}\n", .{world.human_enter()});

    // Input loop
    const stdin = std.io.getStdIn().reader();
    var line_buf: [1024]u8 = undefined;

    while (true) {
        std.debug.print("> ", .{});
        const maybe_line = try stdin.readUntilDelimiterOrEof(&line_buf, '\n');
        const line = maybe_line orelse break; // EOF
        const response = world.human_act(line);
        std.debug.print("{s}\n", .{response});
    }
}
```