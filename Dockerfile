FROM alpine:latest
RUN apk add --no-cache zig musl-dev gcc emscripten

WORKDIR /mud-arena
COPY . .

# Build Zig native
RUN zig build -Doptimize=ReleaseSmall

# Build WASM
RUN emcc -O3 -s WASM=1 -s EXPORTED_RUNTIME_METHODS='["ccall","cwrap"]' -s EXPORTED_FUNCTIONS='["_mud_init","_mud_command","_mud_tick","_mud_get_output","_mud_human_enter","_mud_human_act","_mud_measure"]' -o mud_arena.js src/wasm_mud.c

EXPOSE 7778 7779
CMD ["./zig-out/bin/mud-arena"]
