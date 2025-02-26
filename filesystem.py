class EmulatedDisk:
    def __init__(self):
        self.disk = [[0] * 512 for _ in range(64)]  # 2D array of 64 blocks of 512 bytes each
        self.bitmap = self.disk[0] = [0] * 64  # 64 bits each representing 1 block

    def __getitem__(self, i):
        return self.disk[i]
    
    def __setitem__(self, i, e):
        self.disk[i] = e   

    def read_block(self, block_index: int):
        if block_index < 0 or block_index > 63:
            raise IndexError("Block index out of range.")

        return self.disk[block_index]

    def write_block(self, block_index: int, data: list):
        if block_index < 0 or block_index > 63:
            raise IndexError("Block index out of range.")
        
        if len(data) != 512:
            raise ValueError("Input array data must be 512 bytes.")

        self.disk[block_index] = list(data)

    def block_free(self, block_index: int) -> bool:
        return self.bitmap[block_index] == 0

class FileSystem:
    def __init__(self):
        self.init()

    def init(self):
        self.disk = EmulatedDisk()
        self.bitmap = self.disk.bitmap

        # Bitmap: mark blocks 0 to 7 as occupied (1), rest are free (0)
        for i in range(8):
            self.bitmap[i] = 1

        # File descriptors: each block 1-6 holds 32 each
        for i in range(1, 7):
            self.disk[i] = [[-1, 0, 0, 0] for _ in range(32)]
        
        self.descriptors = self.disk[1:7]

        self.I = [0] * 512
        self.O = [0] * 512
        self.M = [0] * 512

        self.oft = [{'buffer': [0] * 512, 'current_pos': -1, 'file_size': 0, 'descriptor_index': 0} for _ in range(4)]

        self.directory = self.disk[7] = [["", 0] for _ in range(64)]

        self.descriptors[0][0] = [0, 7, 0, 0]  # Directory: file_length=0, block1=7

        # Open directory in oft[0]
        self.oft[0]["buffer"] = self.disk.read_block(7)
        self.oft[0]["current_pos"] = 0
        self.oft[0]["file_size"] = 0
        self.oft[0]["descriptor_index"] = 0

    def create(self, filename: str) -> int:
        if len(filename) > 3:
            return -1  # Error: filename too long
        
        # Check if file already exists
        for entry in self.directory:
            if entry[0] == filename:
                return -1  # Error: file already exists
        
        # Search directory for free entry
        dir_entry = None
        dir_index = -1
        for i, entry in enumerate(self.directory):
            if entry[0] == "":  # Free entry
                dir_entry = entry
                dir_index = i
                break
        
        if dir_entry is None:
            return -1  # Error: directory full
        
        # Find free descriptor
        desc_index = -1
        for i in range(192):  # 6 blocks * 32 descriptors
            block = i // 32
            offset = i % 32
            if self.descriptors[block][offset][0] == -1:  # Free descriptor
                desc_index = i
                break
        
        if desc_index == -1:
            return -1  # Error: no free descriptors
        
        # Find free block
        block_num = -1
        for i in range(8, 64):
            if self.bitmap[i] == 0:
                block_num = i
                self.bitmap[i] = 1  # Mark as used
                break
        
        if block_num == -1:
            return -1  # Error: no free blocks
        
        # Initialize descriptor
        block_idx = desc_index // 32
        desc_offset = desc_index % 32
        self.descriptors[block_idx][desc_offset] = [0, block_num, 0, 0]  # length=0, first block allocated
        
        # Update directory
        self.directory[dir_index] = [filename, desc_index]
        
        # Write updated directory to disk
        self.disk[7] = self.directory
        
        return 0  # Success

    def destroy(self, filename: str) -> int:
        # Find file in directory
        dir_entry = None
        dir_index = -1
        for i, entry in enumerate(self.directory):
            if entry[0] == filename:
                dir_entry = entry
                dir_index = i
                break
        
        if dir_entry is None:
            return -1  # Error: file not found
        
        desc_index = dir_entry[1]
        block_idx = desc_index // 32
        desc_offset = desc_index % 32
        descriptor = self.descriptors[block_idx][desc_offset]
        
        # Free all blocks used by file
        for block_num in descriptor[1:4]:
            if block_num != 0:
                self.bitmap[block_num] = 0
        
        # Mark descriptor as free
        self.descriptors[block_idx][desc_offset] = [-1, 0, 0, 0]
        
        # Mark directory entry as free
        self.directory[dir_index] = ["", 0]
        
        # Write updated directory to disk
        self.disk[7] = self.directory
        
        return 0  # Success

    def open(self, filename: str) -> int:
        # Find file in directory
        desc_index = -1
        for entry in self.directory:
            if entry[0] == filename:
                desc_index = entry[1]
                break
        
        if desc_index == -1:
            return -1  # Error: file not found
        
        # Check if file is already open
        for i in range(4):  # Check all OFT entries
            if self.oft[i]["descriptor_index"] == desc_index and self.oft[i]["current_pos"] != -1:
                return -1  # Error: file already open
        
        # Find free OFT entry
        oft_index = -1
        for i in range(1, 4):  # Skip index 0 (reserved for directory)
            if self.oft[i]["current_pos"] == -1:
                oft_index = i
                break
        
        if oft_index == -1:
            return -1  # Error: no free OFT entries
        
        # Get descriptor
        block_idx = desc_index // 32
        desc_offset = desc_index % 32
        descriptor = self.descriptors[block_idx][desc_offset]
        
        # Initialize OFT entry
        self.oft[oft_index] = {
            "buffer": self.disk.read_block(descriptor[1]),  # Read first block
            "current_pos": 0,
            "file_size": descriptor[0],
            "descriptor_index": desc_index
        }
        
        return oft_index

    def close(self, index: int) -> int:
        if index < 0 or index > 3 or self.oft[index]["current_pos"] == -1:
            return -1  # Error: invalid index or already closed
        
        # Get descriptor
        desc_index = self.oft[index]["descriptor_index"]
        block_idx = desc_index // 32
        desc_offset = desc_index % 32
        descriptor = self.descriptors[block_idx][desc_offset]
        
        # Write final buffer to disk
        current_block_index = self.oft[index]["current_pos"] // 512
        if current_block_index == 0:
            current_block = descriptor[1]
        else:
            current_block = descriptor[1 + current_block_index]
        
        if current_block != 0:
            self.disk[current_block] = self.oft[index]["buffer"]
        
        # Mark OFT entry as free
        self.oft[index] = {"buffer": [0] * 512, "current_pos": -1, "file_size": 0, "descriptor_index": 0}
        
        return 0

    def read(self, index: int, mem_area: list, count: int) -> int:
        if index < 0 or index > 3 or self.oft[index]["current_pos"] == -1:
            return -1  # Error: invalid index or file not open
        
        # Get descriptor
        desc_index = self.oft[index]["descriptor_index"]
        block_idx = desc_index // 32
        desc_offset = desc_index % 32
        descriptor = self.descriptors[block_idx][desc_offset]
        
        bytes_read = 0
        while bytes_read < count:
            # Check if we've reached EOF
            if self.oft[index]["current_pos"] >= descriptor[0]:
                break
            
            # Get current block number and position
            current_block_index = self.oft[index]["current_pos"] // 512
            buffer_pos = self.oft[index]["current_pos"] % 512
            
            # If we need to load a different block
            if current_block_index > 0 and bytes_read == 0:
                block_num = descriptor[1 + current_block_index]
                if block_num != 0:
                    self.oft[index]["buffer"] = self.disk.read_block(block_num)
            
            # Read from buffer
            mem_area[bytes_read] = self.oft[index]["buffer"][buffer_pos]
            bytes_read += 1
            self.oft[index]["current_pos"] += 1
            
            # If we've reached end of current block, load next block
            if self.oft[index]["current_pos"] % 512 == 0 and bytes_read < count:
                next_block_index = self.oft[index]["current_pos"] // 512
                if next_block_index < 3:  # Max 3 blocks per file
                    block_num = descriptor[1 + next_block_index]
                    if block_num != 0:
                        self.oft[index]["buffer"] = self.disk.read_block(block_num)
                    else:
                        break
                else:
                    break
        
        return bytes_read

    def write(self, index: int, mem_area: list, count: int) -> int:
        if index < 0 or index > 3 or self.oft[index]["current_pos"] == -1:
            return -1  # Error: invalid index or file not open
        
        # Get descriptor
        desc_index = self.oft[index]["descriptor_index"]
        block_idx = desc_index // 32
        desc_offset = desc_index % 32
        descriptor = self.descriptors[block_idx][desc_offset]
        
        bytes_written = 0
        while bytes_written < count:
            # Get current block number and position within block
            current_block_index = self.oft[index]["current_pos"] // 512
            
            # Check if we've exceeded max file size (3 blocks)
            if current_block_index >= 3:
                # Return bytes written so far, even if less than requested
                return bytes_written
            
            buffer_pos = self.oft[index]["current_pos"] % 512
            
            # If we need a new block
            if buffer_pos == 0 and current_block_index > 0:
                # Find a free block
                new_block = self.find_free_block()
                if new_block == -1:
                    return bytes_written  # Return bytes written so far if no more blocks available
                
                # Update descriptor with new block
                descriptor[1 + current_block_index] = new_block
                # Mark block as used
                self.bitmap[new_block] = 1
                # Load new block into buffer
                self.oft[index]["buffer"] = [0] * 512
            
            # Write to buffer
            self.oft[index]["buffer"][buffer_pos] = mem_area[bytes_written]
            bytes_written += 1
            self.oft[index]["current_pos"] += 1
            
            # If buffer is full or this is the last byte, write back to disk
            if buffer_pos == 511 or bytes_written == count:
                block_num = descriptor[1 + current_block_index]
                if block_num != 0:
                    self.disk.write_block(block_num, self.oft[index]["buffer"])
            
            # Update file size in descriptor if we've written beyond current size
            if self.oft[index]["current_pos"] > descriptor[0]:
                descriptor[0] = self.oft[index]["current_pos"]
        
        return bytes_written

    def seek(self, index: int, pos: int) -> int:
        if index < 0 or index > 3 or self.oft[index]["current_pos"] == -1:
            return -1  # Error: invalid index or file not open
        
        # Get descriptor
        desc_index = self.oft[index]["descriptor_index"]
        block_idx = desc_index // 32
        desc_offset = desc_index % 32
        descriptor = self.descriptors[block_idx][desc_offset]
        
        if pos < 0 or pos > descriptor[0]:
            return -1  # Error: invalid position
        
        # Calculate which block we need
        new_block_index = pos // 512
        
        # Load the correct block into buffer
        if new_block_index < 3:  # Max 3 blocks per file
            block_num = descriptor[1 + new_block_index]
            if block_num != 0:
                self.oft[index]["buffer"] = self.disk.read_block(block_num)
            else:
                return -1  # Error: block not allocated
        else:
            return -1  # Error: position beyond file limit
        
        self.oft[index]["current_pos"] = pos
        return pos

    def list_directory(self) -> list:
        dir_contents = []
        for entry in self.directory:
            if entry[0] != "":  # If entry is not free
                desc_index = entry[1]
                block_idx = desc_index // 32
                desc_offset = desc_index % 32
                descriptor = self.descriptors[block_idx][desc_offset]
                dir_contents.append((entry[0], descriptor[0]))  # (filename, length)
        return dir_contents

    def find_free_block(self) -> int:
        for i in range(8, 64):
            if self.bitmap[i] == 0:
                return i
        return -1

def shell(fs=None, input_file=None, output_file=None):
    if fs is None:
        fs = FileSystem()
    
    # Memory array M for read/write operations
    M = [0] * 1024  # 1KB of memory
    
    # Setup output handling
    output_stream = None
    if output_file:
        try:
            output_stream = open(output_file, 'w')
        except IOError:
            print(f"Error: Could not open output file {output_file}")
            return
    
    def write_output(message):
        if output_stream:
            output_stream.write(message + '\n')
            output_stream.flush()
        else:
            print(message)
    
    def process_command(line):
        nonlocal M
        try:
            tokens = line.strip().split()
            if not tokens:
                return
            
            cmd = tokens[0].lower()
            
            if cmd == 'cr' and len(tokens) == 2:
                name = tokens[1]
                if fs.create(name) == 0:
                    write_output(f"{name} created")
                else:
                    write_output("error")
            
            elif cmd == 'de' and len(tokens) == 2:
                name = tokens[1]
                if fs.destroy(name) == 0:
                    write_output(f"{name} destroyed")
                else:
                    write_output("error")
            
            elif cmd == 'op' and len(tokens) == 2:
                name = tokens[1]
                index = fs.open(name)
                if index >= 0:
                    write_output(f"{name} opened {index}")
                else:
                    write_output("error")
            
            elif cmd == 'cl' and len(tokens) == 2:
                index = int(tokens[1])
                if fs.close(index) == 0:
                    write_output(f"{index} closed")
                else:
                    write_output("error")
            
            elif cmd == 'rd' and len(tokens) == 4:
                index = int(tokens[1])
                mem_pos = int(tokens[2])
                count = int(tokens[3])
                read_buffer = [0] * count
                bytes_read = fs.read(index, read_buffer, count)
                if bytes_read >= 0:
                    # Copy to memory M
                    for i in range(bytes_read):
                        M[mem_pos + i] = read_buffer[i]
                    write_output(f"{bytes_read} bytes read from {index}")
                else:
                    write_output("error")
            
            elif cmd == 'wr' and len(tokens) == 4:
                index = int(tokens[1])
                mem_pos = int(tokens[2])
                count = int(tokens[3])
                # Copy from memory M
                write_buffer = M[mem_pos:mem_pos + count]
                bytes_written = fs.write(index, write_buffer, count)
                if bytes_written > 0:
                    write_output(f"{bytes_written} bytes written to {index}")
                else:
                    write_output("error")
            
            elif cmd == 'sk' and len(tokens) == 3:
                index = int(tokens[1])
                pos = int(tokens[2])
                if fs.seek(index, pos) >= 0:
                    write_output(f"position is {pos}")
                else:
                    write_output("error")
            
            elif cmd == 'dr' and len(tokens) == 1:
                contents = fs.list_directory()
                if contents:
                    output = " ".join(f"{name} {length}" for name, length in contents)
                    write_output(output)
                else:
                    write_output("")  # Empty directory
            
            elif cmd == 'in' and len(tokens) == 1:
                fs.init()
                M[:] = [0] * 1024  # Reset cache
                write_output("system initialized")
            
            elif cmd == 'rm' and len(tokens) == 3:
                mem_pos = int(tokens[1])
                count = int(tokens[2])

                # Only output if the memory location has been written to                
                output = "".join(c for c in (chr(M[mem_pos + i]) for i in range(count)) if c != '\0')
                
                write_output(output)
            
            elif cmd == 'wm' and len(tokens) >= 3:
                mem_pos = int(tokens[1])
                # Join all remaining tokens as the string to write
                input_str = " ".join(tokens[2:])
                # Copy string to memory M
                for i, char in enumerate(input_str):
                    M[mem_pos + i] = ord(char)
                write_output(f"{len(input_str)} bytes written to M")
            
            else:
                write_output("error")
                
        except (IndexError, ValueError) as e:
            write_output("error")
    
    try:
        if input_file:
            try:
                with open(input_file, 'r') as f:
                    for line in f:
                        process_command(line)
            except FileNotFoundError:
                write_output(f"Error: Could not open input file {input_file}")
        else:
            while True:
                try:
                    line = input("$ ")
                    process_command(line)
                except (KeyboardInterrupt, EOFError):
                    break
    finally:
        if output_stream:
            output_stream.close()

if __name__ == "__main__":
    import sys
    
    input_file = None
    output_file = None
    
    argc = len(sys.argv)
    if argc == 2:  # python filesystem.py input_file
        input_file = sys.argv[1]
    elif argc == 3:  # python filesystem.py input_file output_file
        input_file = sys.argv[1]
        output_file = sys.argv[2]
    elif argc != 1:  # not just python filesystem.py
        print("Usage: python filesystem.py [input_file] [output_file]")
        sys.exit(1)
    
    shell(input_file=input_file, output_file=output_file)