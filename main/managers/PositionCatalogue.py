from typing import Dict, Optional, List
import pickle 

class PositionCatalogue:
    """
    Represents a trading position and manages a collection of positions.
    
    Attributes:
        positions (Dict[str, Dict]): A dictionary mapping symbols to their position details.
    """
    def __init__(self):
        """
        Initialize the Position manager with an empty collection of positions.
        """
        self.positions: Dict[str, Dict] = {}  # Symbol -> Position details mapping

    def add_position(self, symbol: str, average_buy_price: float, pnl: float,
                     size_in_dollars: float, size_in_quote: float, limit_orders: Dict[str, str], ttp_active: bool):
        """
        Add a new position to the collection.
        
        Args:
            symbol (str): The trading symbol (e.g., "BTC").
            average_buy_price (float): The average price at which the position was bought.
            leverage (float): The leverage used for the position.
            size_in_dollars (float): The size of the position in dollars.
            size_in_quote (float): The size of the position in quote currency.
            limit_orders (Dict[str, str]): A dictionary of limit order IDs and their statuses.
        
        Raises:
            ValueError: If a position with the same symbol already exists.
        """
        if symbol in self.positions:
            raise ValueError(f"Position with symbol '{symbol}' already exists.")
        self.positions[symbol] = {
            "symbol": symbol,
            "average_buy_price": average_buy_price,
            "pnl": pnl,
            "size_in_dollars": size_in_dollars,
            "size_in_quote": size_in_quote,
            "limit_orders": limit_orders,
            "ttp_active": ttp_active
        }

    def get_position(self, symbol: str) -> Optional[Dict]:
        """
        Retrieve a position by its symbol.
        
        Args:
            symbol (str): The symbol of the position to retrieve.
        
        Returns:
            Optional[Dict]: The position details as a dictionary if it exists, None otherwise.
        """
        return self.positions.get(symbol)

    def update_position(self, symbol: str, **kwargs):
        """
        Update one or more parameters of an existing position.
        
        Args:
            symbol (str): The symbol of the position to update.
            kwargs: Key-value pairs of attributes to update.
        
        Raises:
            KeyError: If no position with the given symbol exists.
        """
        if symbol not in self.positions:
            raise KeyError(f"No position found with symbol '{symbol}'.")
        self.positions[symbol].update(kwargs)

    def delete_position(self, symbol: str):
        """
        Delete a position from the collection.
        
        Args:
            symbol (str): The symbol of the position to delete.
        
        Raises:
            KeyError: If no position with the given symbol exists.
        """
        if symbol not in self.positions:
            raise KeyError(f"No position found with symbol '{symbol}'.")
        del self.positions[symbol]

    def has_position(self, symbol: str) -> bool:
        """
        Check if a position with the given symbol exists in the collection.
        
        Args:
            symbol (str): The symbol to check.
        
        Returns:
            bool: True if the position exists, False otherwise.
        """
        return symbol in self.positions
    
    def save_to_file(self, file_path: str):
        """
        Save the current positions to a binary file using Pickle.
        
        Args:
            file_path (str): The path to the file where the data will be saved.
        """
        try:
            with open(file_path, "wb") as file:
                pickle.dump(self.positions, file)
            print(f"Positions successfully saved to {file_path}")
        except Exception as e:
            print(f"Error saving positions to file: {e}")

    def load_from_file(self, file_path: str):
        """
        Load positions from a binary file using Pickle.

        Args:
            file_path (str): The path to the file from which to load the data.
        """
        try:
            with open(file_path, "rb") as file:
                loaded_data = pickle.load(file)
            if not isinstance(loaded_data, dict):
                raise ValueError("Invalid data format in file. Expected a dictionary.")
            self.positions = loaded_data
            print(f"Positions successfully loaded from {file_path}")
        except FileNotFoundError:
            print(f"No saved positions found. Initializing with an empty collection.")
            self.positions = {}  # Ensure positions is initialized as an empty dictionary
        except Exception as e:
            print(f"Error loading positions from file: {e}")

    def __repr__(self):
        """
        Return a string representation of the Position manager.
        
        Returns:
            str: A string representation showing the symbols in the collection.
        """
        return f"Position(positions={list(self.positions.keys())})"
    
    def transform_dataset(data: dict) -> dict:
        """
        Transforms a dictionary of keys and order IDs into a dictionary where
        the order IDs are the keys, and their values are set to 'filled'.
        This function is used to transform limit orders data from create batch limit order to this format that will be saved in dataset

        Args:
            data (dict): A dictionary where keys are arbitrary and values are order IDs.

        Returns:
            dict: A dictionary where order IDs are keys, and values are 'filled'.
        """
        return {int(order_id): "filled" for order_id in data.values()}
    
    def inverse_transform_dataset(order_status: Dict[int, str], deviations: List[float]) -> Dict[float, str]:
        """
        Transforms a dictionary of order IDs and their statuses into a dictionary where
        deviations are the keys, and the order IDs (as strings) are the values.

        Args:
            order_status (Dict[int, str]): A dictionary where keys are order IDs and values are their statuses.
            deviations (List[float]): A list of deviations to use as keys in the output dictionary.

        Returns:
            Dict[float, str]: A dictionary where deviations are keys, and order IDs (as strings) are values.

        Raises:
            ValueError: If the length of deviations does not match the number of orders in order_status.
        """
        # Extract the order IDs from the input dictionary
        order_ids = list(order_status.keys())

        # Check if the lengths match
        if len(deviations) != len(order_ids):
            raise ValueError("The length of deviations must match the number of orders in order_status.")

        # Create the inverse mapping
        return {deviation: str(order_id) for deviation, order_id in zip(deviations, order_ids)}