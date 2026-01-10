📌 Blockchain Integration Error — Explanation for README
🔴 Issue Encountered

During the integration of the blockchain module with the Spring Boot backend, the application successfully completed the verification process but failed while attempting to store the verification proof on the blockchain.

The API response returned:

{
  "status": "VERIFIED",
  "confidenceScore": 0.85,
  "blockchainTx": "FAILED_TO_WRITE"
}


This indicated that the verification logic was working correctly, but the blockchain transaction was failing at runtime.

🔍 Root Cause

The error occurred because of a data type mismatch between the backend and the smart contract.

The smart contract function expected a parameter of type bytes32.

Initially, the backend was sending a byte array that was not exactly 32 bytes long.

Web3j strictly validates ABI types, and when the byte length does not match bytes32, it throws a runtime exception:

java.lang.UnsupportedOperationException:
Input byte array must be in range 0 < M <= 32 and length must match type


As a result, the transaction failed before it could be submitted to the blockchain.

🛠 Solution Implemented

To fix this issue, the backend was updated to:

Generate a SHA-256 hash of the verification proof.

Explicitly ensure the hash is exactly 32 bytes.

Pass the corrected bytes32 value to the smart contract.

Final Fix in Backend
MessageDigest md = MessageDigest.getInstance("SHA-256");
byte[] hashBytes = md.digest(data.getBytes(StandardCharsets.UTF_8));
byte[] bytes32 = Arrays.copyOf(hashBytes, 32);


This guarantees compatibility with the Solidity bytes32 type and prevents ABI encoding errors.

🎯 Key Takeaway

This issue highlights an important lesson in Web3 backend development:

Smart contracts are strict about data types, and even small mismatches between backend encoding and Solidity types can cause runtime transaction failures.

By resolving this, the system now correctly prepares cryptographic proofs for on-chain storage while keeping sensitive verification logic off-chain.
