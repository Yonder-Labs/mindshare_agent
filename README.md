# Mindshare Trading Agent

Mindshare Trading Agent is an autonomous smart agent written in Python that runs securely inside a Trusted Execution Environment (TEE). It continuously analyzes the mindshare of tokens using the Kaito API, makes strategic trading decisions with the help of large language models (LLMs), and executes those trades on the [NEAR Protocol](https://docs.near.org/) using chain signatures and the [NEAR Intents protocol](https://near.org/intents).

The agent is registered onchain in a NEAR smart contract and is cryptographically verified to be running in a secure environment (TEE). Based on mindshare metrics and asset balances, it autonomously evaluates and executes trades on a recurring schedule.

## ✨ Features
- 🔍 Automated mindshare analysis.
Continuously monitors token popularity and trends via Kaito API

- 🧠 Smart trading decisions.
Uses NEAR AI and LLMs to determine optimal trades based on current market signals

- 🔐 Secure trade execution.
All trades are signed with the ERC-191 standard using chain signatures

- 🔁 Near intents integration.
Publishes and settles trades through the NEAR Intents solver bus

- 💼 Portfolio management.
Tracks and manages balances across supported assets

- ⏱️ Scheduled execution.
Runs periodically based on a configurable time interval

- 💰 Multi-asset support.
Supports trading of major tokens including NEAR, USDC, ETH, BTC, SOL, XRP, and TRUMP.
Additional ERC-20 tokens can be added by customizing the ASSET_MAP configuration. [View supported tokens on Near Intents](https://api-mng-console.chaindefuser.com/api/tokens)

## Overview

This project seamlessly integrates cutting-edge decentralized technologies to deliver an intelligent, privacy-preserving, and fully automated trading agent:

- 🔗 NEAR Protocol.
Acts as the core execution layer for trades and on-chain interactions. It also manages the agent's identity and verifies that its logic is running within a TEE. Additionally, NEAR smart contracts handle the MPC-based signing of cross-chain transactions via Chain Signatures.

- 🤖 NEAR AI & LLMs.
The agent uses Large Language Models (LLMs) through the NEAR AI platform to reason about market conditions and determine optimal trading strategies. NEAR AI enables agents that can autonomously adapt, remember past actions, interact with external tools, and collaborate with other agents in a decentralized environment.

- 🧠 Kaito API.
Provides real-time access to proprietary mindshare and sentiment data across the crypto ecosystem. Kaito’s high-fidelity dataset includes quantifiable social metrics and in-depth analytics, allowing the agent to identify trending assets and anticipate market shifts with enhanced intelligence.

- 🔏 Chain Signatures (ERC-191 + MPC).
Trades are signed off-chain using Chain Signatures, a system based on ERC-191 and Multi-Party Computation (MPC). This allows NEAR accounts—smart contracts or users—to securely sign transactions for other blockchains without exposing private keys. Chain Signatures enable:

    - ✅ Cross-chain operations from a single NEAR account
    - ✅ Simplified key management and reduced wallet complexity
    - ✅ Decentralized, secure signing via MPC (no single point of failure)

- 🛠️ NEAR Intents.
A powerful abstraction layer for DeFi operations. The agent expresses high-level intents (e.g., "swap NEAR to USDC if price is favorable") which are then fulfilled by off-chain solvers. The protocol takes care of routing, matching, and settlement across chains—allowing for seamless automation of complex financial logic without direct smart contract calls.

- 🧪 Trusted Execution Environment (TEE) via Phala Cloud.
Inspired by the Shade Agent Template, the agent’s execution logic runs securely inside a TEE enclave. This ensures:

    - 🔐 Confidentiality of strategies and credentials
    - 🧩 Verifiable execution proof onchain
    - 🛡️ Protection against tampering—even on untrusted infrastructure

    By leveraging TEE technology from Phala Network, the system guarantees trustless execution of sensitive logic and decisions, without exposing the underlying logic to the public or the host machine.

## System Architecture 

Below is a high-level overview of how the agent works internally, along with the project structure that supports each component:

### Agent Execution Workflow

![Agent Workflow](/images/flow.png)

This agent runs inside a secure enclave (TEE) and automates trading decisions based on token mindshare in NEAR Intents. Here's the full execution flow:

- **Agent worker.**
The agent starts inside a TEE, creates an ephemeral NEAR account, and checks if it is already registered on the Agent Worker smart contract by verifying its codehash. Once registered, future interactions skip this verification.

- **Token Balances & Mindshare Retrieval.**
After registered, the agent fetches token balances deposited in the NEAR Intents contract and retrieves mindshare data from the Kaito API.

- **Trade Decision & Quote Generation.**
The AI module (LLM) analyzes token mindshare and balances to generate trading decisions. These are turned into a structured quote, which is required by the solver bus.

- **Secure Signing via MPC.**
The quote is sent to the Agent Worker contract, which verifies the agent’s identity via its codehash and forwards the signing request to the v1.signer contract. The v1.signer coordinates with the MPC service to securely sign the payload.

> ℹ️ **Note:** The `Agent Worker Smart Contract` is maintained separately at [Yonder-Labs/mindshare_contract](https://github.com/Yonder-Labs/mindshare_contract).

- **Signature Validation & Intent Formation.**
Once the signature components (r, s, scalar) are returned, the agent validates the signature and constructs a valid intent.

- **Intent Publication.**
The agent sends the signed intent to the solver bus, where it becomes available for execution.

### 🧩 Component Responsibilities

| Component           | Description |
|---------------------|-------------|
| **Scheduler**        | Triggers the periodic execution of the agent. |
| **Agent (TEE)**      | Runs in a secure enclave, fetches balances, mindshare, and coordinates the workflow. |
| **Quote Module**     | Builds standardized trade quotes from decisions. |
| **Chain Signatures** | Handles secure signature flow via `Agent Worker` and `v1.signer` contracts. |
| **Intent Publisher** | Publishes the final signed intent to NEAR Intents. |
| **Worker Monitor**   | Watches for intent execution and updates the state accordingly. |


### Project Structure

```
src/
├── agent/              # Core agent logic: LLM integration, Kaito API, and TEE orchestration
├── contract/           # Smart contract interfaces and utilities to call the agent worker smart contract
├── quote/              # Quote generation, formatting, and validation
├── scheduler/          # Timed execution and job coordination
├── worker/             # Ephemeral account and keypair lifecycle management
└── tappd/              # TEE-specific runtime operations and attestation
```

## Pre-configuration Requirements

Before running the agent, you'll need to set up several accounts and services:

1. **NEAR Account Setup**
   - Create a [NEAR wallet](https://wallet.near.org/)
   - Fund your wallet with NEAR tokens for transaction fees
   - Create a full access key for your account

2. **NEAR AI Account**
   - Visit [NEAR AI](https://docs.near.ai/agents/quickstart/#prerequisites)
   - Follow the instructions to install NEAR AI CLI.
   - Logged in with your Near Wallet
   - Set up your AI model preferences

3. **NEAR Intents Configuration**
   - Visit [NEAR Intents](https://app.near-intents.org)
   - Deposit assets you want to trade

4. **Kaito API Access** 
   - Sign up at [Kaito](https://www.kaito.ai/kaito-api)
   - Generate your API key
   - Configure rate limits as needed

5. **Phala Cloud Setup**
   - Create account at [Phala Cloud](https://cloud.phala.network/)  
   - Generate necessary credentials

6. **Python Environment**
   - Install Python 3.8+
   - Install required packages (see `requirements.txt`)

7. **Asset Configuration**
Assets can be configured in `src/constants.py`:

```python
ASSET_MAP = {
    'USDC': { 
        'token_id': 'nep141:eth-0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48.omft.near',
        'decimals': 6,
        'blockchain': 'eth',
        'symbol': 'USDC',
        'price': 0.999795,
        'price_updated_at': "2025-03-25T15:11:40.065Z",
        'contract_address': "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    },
    'NEAR': {
        'token_id': 'wrap.near',
        'decimals': 24,
    },
}
```

## Installation

1. Clone the repository:

```bash
git clone https://github.com/hasselalcala/mindshare_agent
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set up environment variables:

```bash
cp .env.sample .env
```

Required environment variables:

```bash
# Scheduler vars
KAITO_API_KEY=<api_key>
INTENT_ACCOUNT_ID=<account_id> # @dev account id for signing intents
INTENT_PRIVATE_KEY=<private_key> # @dev private key for signing intents
NETWORK="testnet|mainnet" # @dev testnet not fully supported yet
SCHEDULE_INTERVAL= # @dev interval for agent execution (in seconds)
USE_MOCK_MINDSHARE="true|false" # @dev use mock mindshare data from kaito api

# Contract vars
USE_STATIC_ACCOUNT="true|false" # @dev use static account for signing intents
SIGN_INTENT_CONTRACT=<contract_id>.near # @dev contract id for signing intents using MPC contract
SIGNER_PUBLIC_KEY_USING_MINDSHARE_ACCOUNT=<derived_public_key> # @dev value is derived from derived_public_key method using MPC contract
AGENT_ID=<account_id> # @dev account id for agent just for development purposes
AGENT_KEY=ed25519:<private_key> # @dev private key for agent just for development purposes
```

## 🚀 Usage

> ⚠️ **Before starting the agent**, make sure the `Agent Worker Smart Contract` is deployed and its address is correctly set in your `.env` file (via `SIGN_INTENT_CONTRACT`). You can deploy or view the contract at [Yonder-Labs/mindshare_contract](https://github.com/Yonder-Labs/mindshare_contract).

### Running the agent locally.

The agent can be run locally to test its logic, interact with the deployed MPC signer contract, and validate the full quote-signing process. In this mode:

- ✅ It runs outside of a TEE
- ✅ It interacts with the MPC signer smart contract and MPC service
- ❌ It cannot publish intents, since NEAR Intents is not available on testnet

1. Start the scheduler:

```bash
python src/scheduler/scheduler.py
```

2. Expected behavior:
- Uses mock mindshare data from the Kaito API (if USE_MOCK_MINDSHARE=true)
- Uses a static NEAR account and private key set in .env
- Sends the quote to the Agent Worker contract, which routes it to v1.signer for MPC signature  
- Receives and verifies the signature (r, s, scalar)
- Forms a valid intent, but does not publish it due to the lack of NEAR Intents testnet
- Outputs all steps to the console for inspection

💡 This mode is useful for validating:
- Mindshare flow
- Quote generation
- MPC signature flow
- Contract interactions

### Running the Agent in Production (TEE + MPC + Intents)

To run the agent securely in production—within a Trusted Execution Environment (TEE), with MPC signing, and publishing intents to NEAR Intents on mainnet—follow these steps:

1. Build the Docker image for deployment:

```bash
docker build -t <docker_username>/mindshare-agent:latest .
```

2. Push docker image in Docker Hub to generate agent's codehash:

```bash
docker push <docker_username>/mindshare-agent:latest
```
This will be used to generate the codehash (a SHA256 hash of the image), which is required for registration on the agent smart contract.

3. Register the agent on-chain:
Use the approve_codehash method from the Agent Worker smart contract to whitelist the codehash you obtained:

```bash 
   near call $SIGN_INTENT_CONTRACT approve_codehash '{"codehash": "your_codehash"}' --accountId $SIGN_INTENT_CONTRACT
```
4. Create docker-compose.yml.
This will be used by Phala Cloud to deploy your agent containerized with the correct environment configuration and TEE socket.

```
services:
  mindshare-agent:
    platform: linux/amd64  
    image: <docker_username>/mindshare-agent:latest@sha256:<codehash>
    container_name: mindshare-agent
    environment:
      - PYTHONPATH=/app
      - PYTHONUNBUFFERED=1
      - KAITO_API_KEY=${KAITO_API_KEY}
      - INTENT_ACCOUNT_ID=${INTENT_ACCOUNT_ID}
      - INTENT_PRIVATE_KEY=${INTENT_PRIVATE_KEY}
      - NETWORK=${NETWORK}
      - SCHEDULE_INTERVAL=${SCHEDULE_INTERVAL}
      - USE_STATIC_ACCOUNT=${USE_STATIC_ACCOUNT}
      - SIGN_INTENT_CONTRACT=${SIGN_INTENT_CONTRACT}
      - SIGNER_PUBLIC_KEY_USING_MINDSHARE_ACCOUNT=${SIGNER_PUBLIC_KEY_USING_MINDSHARE_ACCOUNT}
      - USE_MOCK_MINDSHARE=${USE_MOCK_MINDSHARE}
      - AGENT_ID=${AGENT_ID}
      - AGENT_KEY=${AGENT_KEY}
    ports:
      - '8000:8000'
    volumes:
      - /var/run/tappd.sock:/var/run/tappd.sock
    restart: always

```
5. Deploy the Agent on Phala Cloud

- Go to Phala Cloud
- Upload the docker-compose.yml
- Provide your .env variables through the dashboard
- Launch the instance and monitor registration logs (look for codehash match and successful connection to the smart contract)

Once the worker is running:

- ✅ The agent verifies registration on-chain
- 🔁 Periodically fetches balances and mindshare
- 💡 Makes trade decisions using LLM + Kaito
- 🖋️ Generates & signs quotes using MPC
- 📤 Publishes signed intents to the NEAR Intents mainnet

## Acknowledgments

- [NEAR Protocol](https://docs.near.org/)
- [Kaito API](https://www.kaito.ai/kaito-api)
- [NEAR AI](https://docs.near.ai/)
- [NEAR Intents](https://docs.near-intents.org/near-intents)
- [Chain signatures](https://docs.near.org/chain-abstraction/chain-signatures)
- [Phala Cloud](https://docs.phala.network/)