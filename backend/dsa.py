# backend/dsa.py
import hashlib
from collections import deque

# --- Shared DSA State ---
# Queue for incoming analysis jobs (FIFO)
job_queue = deque()
# Hash table (set) to track hashes of processed content (for deduplication)
seen_hashes = set()

# --- Merkle Tree Class ---
class MerkleTree:
    """
    A simple Merkle Tree implementation to create a root hash
    representing the integrity of a list of data items.
    """
    def __init__(self, data_list):
        """
        Initializes the Merkle Tree.

        Args:
            data_list: A list of data items (will be converted to strings).
        """
        # 1. Create leaf nodes by hashing each individual data item
        self.leaves = [self._hash_data(str(data)) for data in data_list]
        # 2. Build the tree recursively from the leaves to get the final root hash
        self.root_hash = self._build_tree(self.leaves)

    def _hash_data(self, data):
        """Helper function to create a SHA-256 hash of a string."""
        return hashlib.sha256(data.encode('utf-8')).hexdigest()

    def _build_tree(self, nodes):
        """
        Recursively builds the Merkle Tree level by level.
        Hashes pairs of nodes together until only one root hash remains.

        Args:
            nodes: A list of hash strings at the current level.

        Returns:
            The root hash string of the tree (or subtree).
        """
        # Base case: If only one node is left, it's the root (or root of a subtree)
        if len(nodes) == 1:
            return nodes[0]

        new_level = [] # To store the hashes of the next level up
        # Process nodes in pairs
        for i in range(0, len(nodes), 2):
            left = nodes[i]
            # Handle an odd number of nodes: duplicate the last one
            if i + 1 < len(nodes):
                right = nodes[i+1]
            else:
                right = left # Duplicate the last node if it's unpaired

            # Combine the two hashes and hash the result to create the parent node hash
            parent_hash = self._hash_data(left + right)
            new_level.append(parent_hash)

        # Recursively call _build_tree with the newly created level
        return self._build_tree(new_level)

# You could add other standalone DSA functions/classes here if needed later