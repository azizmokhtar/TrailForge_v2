import asyncio
import aiofiles

class SymbolManager:
    def __init__(self, initial_symbols, filename='active_symbols.txt'):
        self.symbols = set(symbol.upper() for symbol in initial_symbols)
        self.pending_removal = set()
        self.lock = asyncio.Lock()
        self.filename = filename

    async def add_symbol(self, symbol):
        async with self.lock:
            symbol_upper = symbol.upper()
            if symbol_upper in self.symbols:
                return False
            self.symbols.add(symbol_upper)
            await self._save()
            return True

    async def remove_symbol(self, symbol):
        async with self.lock:
            symbol_upper = symbol.upper()
            if symbol_upper in self.pending_removal:
                return False  # Already scheduled
            if symbol_upper not in self.symbols:
                return False

            self.symbols.remove(symbol_upper)
            self.pending_removal.add(symbol_upper)
            await self._save()
            return True
    
    async def is_pending_removal(self, symbol):
        async with self.lock:
            return symbol.upper() in self.pending_removal

    async def get_active_symbols(self):
        async with self.lock:
            return [s for s in self.symbols if s not in self.pending_removal]

    async def _save(self):
        """Save symbols to file in compact format"""
        try:
            async with aiofiles.open(self.filename, 'w') as f:
                await f.write('\n'.join(sorted(self.symbols)))
            return True
        except Exception as e:
            print(f"File write error: {e}")
            return False

    async def load(self):
        """Load symbols from file efficiently"""
        try:
            async with aiofiles.open(self.filename, 'r') as f:
                content = await f.read()
            
            if content:
                loaded_symbols = {
                    line.strip().upper() 
                    for line in content.splitlines() 
                    if line.strip()
                }
                async with self.lock:
                    self.symbols = loaded_symbols
            return True
        except FileNotFoundError:
            return False  # Silent fail for initial run
        except Exception as e:
            print(f"File read error: {e}")
            return False
        

#
#
#
#async def initialize_symbol_manager():
#    # Initialize with default symbols and load from file
#    symbol_manager = SymbolManager(["RENDER", "HYPE", "ADA", "AAVE", "SUI"])
#    
#    # Load persisted symbols (if any)
#    await symbol_manager.load()
#    
#    # Return ready-to-use manager
#    return symbol_manager
#