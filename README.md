# File System Emulator for UC Irvine CS 143B

## Overview
This project implements a simplified file system emulator in Python, simulating the core components and operations of a disk-based file system. It provides an interactive shell and supports file creation, deletion, opening, closing, reading, writing, seeking, and directory listing, all managed in memory.

## Architecture and Implementation Details

### Emulated Disk
- The `EmulatedDisk` class simulates a physical disk as a 2D array of 64 blocks, each 512 bytes.
- Block 0 is used as a bitmap for block allocation, where each bit represents the usage status of a block (1 = used, 0 = free).
- Blocks 1-6 store file descriptors (metadata for files), with each block holding 32 descriptors.
- Block 7 is used for the directory, which maps filenames to file descriptors.
- Blocks 8-63 are available for file data.

### File System
- The `FileSystem` class manages the emulated disk and implements the file system logic.
- **Initialization**: Sets up the disk, bitmap, file descriptors, and directory. The directory is always open in the first entry of the Open File Table (OFT).
- **File Descriptors**: Each file has a descriptor that tracks its length and up to three block pointers.
- **Directory**: Implemented as a special file, mapping filenames (up to 3 characters) to descriptor indices.
- **Open File Table (OFT)**: Supports up to 4 concurrently open files (including the directory). Each OFT entry has a buffer, current position, file size, and descriptor index.

### Supported Operations
- `cr <filename>`: Create a new file. Fails if the filename is too long, already exists, or no space is available.
- `de <filename>`: Delete a file and free its blocks and descriptor.
- `op <filename>`: Open a file and assign it to an available OFT entry.
- `cl <index>`: Close the open file at the given OFT index, flushing its buffer to disk.
- `rd <index> <mem_pos> <count>`: Read bytes from the open file into memory.
- `wr <index> <mem_pos> <count>`: Write bytes from memory into the open file.
- `sk <index> <pos>`: Seek to a position in the open file.
- `dr`: List all files in the directory with their sizes.
- `in`: Re-initialize the file system, clearing all files and data.
- `rm <mem_pos> <count>`: Print a string from memory.
- `wm <mem_pos> <string>`: Write a string to memory.

### Shell and Command Processing
- The `shell` function provides an interactive or file-driven command interface.
- Commands are parsed and dispatched to the appropriate file system methods.
- Input and output can be redirected to files.

### Error Handling
- Most commands return `error` if the operation is invalid (e.g., file not found, no free space, invalid index).

## Usage
Run the emulator with:

```
python filesystem.py [input_file] [output_file]
```
- `input_file`: (Optional) File containing commands to execute (default: interactive input)
- `output_file`: (Optional) File to write output to (default: print to console)

## Example Commands
```
cr foo
op foo
wr 1 0 4
cl 1
dr
```

## Notes
- Filenames are limited to 3 characters.
- Maximum 4 open files at a time (including the directory).
- Directory and file metadata are always consistent with the simulated disk state.
- The emulator is self-contained and does not persist data between runs.

---
This emulator is designed for educational use in UC Irvine's CS 143B course to illustrate file system principles and provide hands-on experience with file system operations.
