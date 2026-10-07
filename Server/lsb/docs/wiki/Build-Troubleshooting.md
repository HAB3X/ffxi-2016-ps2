## Build Troubleshooting

## Building from the commandline

_Make sure you have `CMake` available to use in your `PATH` through some means._

The same steps work on Windows and Linux. Run them from the repo root:

```sh
python3 ./tools/build.py
```

Windows: `py -3 .\tools\build.py`

`build.py` is a thin wrapper. It runs these two commands, and you can run them yourself instead:

```sh
cmake --preset default
cmake --build --preset default
```

The `default` preset builds `RelWithDebInfo` configuration. This is the configuration you want for everyday use.

Use the `debug` build preset only when you are chasing a serious problem and need full debug information. A `Debug` build of the map server is many times slower:

```sh
cmake --preset default
cmake --build --preset debug
```

### The presets

All three ways of building read the same `CMakePresets.json`, so they cannot drift apart. Visual Studio shows the presets in its dropdowns, and both `build.py` and `cmake` take `--preset`.

They use **Ninja Multi-Config**: one build directory holds every configuration, and you choose the configuration when you build rather than when you configure.

| Configure preset | Build directory | |
| --- | --- | --- |
| `default` | `build/` | Everything. |
| `tracy` | `build-tracy/` | The Tracy profiler compiled in. See [Performance Profiling with Tracy](Performance-Profiling-with-Tracy). |

| Build preset | Configuration | Use it for |
| --- | --- | --- |
| `default` | `RelWithDebInfo` | Everyday work. |
| `debug` | `Debug` | Chasing a serious problem. Many times slower to run. |
| `release` | `Release` | Fully optimized, no debug info. |
| `tracy` | `RelWithDebInfo` | Profiling. Builds `xi_map_tracy`. |

Configure once, then build whichever configuration you need out of the same directory:

```sh
cmake --preset default
cmake --build --preset default
cmake --build --preset debug
```

`build.py` takes the same names and works out which configure preset each one belongs to:

```sh
python3 ./tools/build.py --preset debug
```

One thing comes with Ninja: CMake uses whichever compiler is on your `PATH`. `build.py` enters the Visual Studio developer environment itself when `cl.exe` is missing, but if you run `cmake` by hand on Windows, **use a Developer PowerShell**. Otherwise the compiler is silently the wrong one if you also have LLVM installed. Check the `CMAKE_CXX_COMPILER` line in the configure output.

### Debug symbols on Windows

Every executable is copied to the repo root after it links, because the server runs from there. The copy records the absolute path of its `.pdb` inside the build tree, so debuggers and crash traces find the symbols without any setup. `STAGE_PDB` (on by default) also copies the `.pdb` beside the executable, which costs about a second per link and lets the root binaries run without the build tree.

Compiler caches are skipped on MSVC. Neither `ccache` nor `sccache` can cache a `/Zi` compile, and `sccache` refuses any file that uses a precompiled header, so a launcher would only add a process per file.

### Changing generator

If a build directory was configured with a different generator, CMake refuses to reuse it:

```txt
CMake Error: Error: generator : Ninja Multi-Config
Does not match the generator used previously: Ninja
Either remove the CMakeCache.txt file and CMakeFiles directory or choose a different binary directory.
```

Delete the directory and configure again. Build directories are disposable and gitignored:

```sh
rm -rf build
cmake --preset default
```

## Troubleshooting

### Paths containing spaces

Previously, the build could fail on paths that contain spaces. While it works _now_, it isn't recommended.

### Drive Letters

It appears as though the build will fail if you try to launch it from a raw drive letter (eg. `D:/`). Instead, use a subfolder: `D:/LSB`.

### External Libraries

On Windows, if you have versions of our external libraries installed on your machine, CMake might try to use them. You'll be able to catch this during configuration when CMake reports:

```
-- MARIADB_LIBRARY: C:\mysql-ver-1.0\lib
-- MARIADB_INCLUDE_DIR: C:\mysql-ver-1.0\include
```

This should be reporting the bundled versions we keep, something like this:

```
-- MARIADB_LIBRARY: C:\dev\lsb\ext\lib\mysql
-- MARIADB_INCLUDE_DIR: C:\dev\lsb\ext\include\mysql
```

If this happens, you can override these paths when you configure CMake:

```sh
cmake --preset default -DMARIADB_INCLUDE_DIR=C:\dev\lsb\ext\include\mysql -DMARIADB_LIBRARY=C:\dev\lsb\ext\lib\libmariadb.lib
```
