# 👑 Sovereign: 3D Distributed Leader Election Simulator

> *"When the king falls, the network crowns another."*

**Sovereign** is a real distributed system paired with a cinematic 3D web dashboard. Five or more independent Python processes ("nodes" or "castles") communicate over raw TCP sockets using newline-delimited JSON and elect a leader using the classic **Bully** and **Ring** algorithms.

When the sovereign leader crashes or is assassinated, heartbeats go silent, surviving nodes detect the failure, and real network messages travel across the kingdom as glowing orbs until a new sovereign is crowned.

---

## 🌟 Why Sovereign Stands Out

- **Real Distributed Processes**: Every castle is its own OS process running an asynchronous TCP server on its own port with real socket communication, real timeouts, and real failure handling—not an in-memory toy or scripted animation.
- **Bully vs. Ring Side-by-Side**: Compare $O(N^2)$ worst-case chatty Bully election with $O(N)$ orderly Ring token passing with empirical numbers.
- **Lamport Logical Clocks**: Every sent and received message updates a monotonic Lamport clock, guaranteeing causal event ordering and replay.
- **Interactive 3D Kingdom**: Built with React Three Fiber and Three.js. Castles breathe, pulse blue during elections, collapse upon death with embers, and wear a rotating golden celestial crown upon coronation.
- **Dynamic Cluster Scaling**: Scale from 3 to 9 nodes live from a slider. Joining nodes announce membership, and lowering the count gracefully retires castles.
- **Fault Injection & Chaos Mode**: Assassinate the king with one click, inject network delay and packet drops, or activate Chaos Mode for random lightning strikes.
- **Analytics & Replay**: Automated benchmark runner (running N rounds per algorithm), Recharts comparisons, step-by-step causal replay, and CSV/JSON export.

---

## 🏛️ System Architecture

```text
[ Browser Dashboard: React 18 + Three.js / R3F + Tailwind ]
            ^                             |
  WebSocket | (Live Events & Telemetry)   | REST (Kill, Revive, Scale, Algo)
            |                             v
    [ Gateway / Orchestrator: FastAPI + SQLite + Uvicorn ]
            ^                             |
  Telemetry |                             | CONTROL (Kill, Revive, Membership)
            |                             v
    +-------------------------------------------------------------+
    |  Node 1 (Port 9001) <---TCP---> Node 2 (Port 9002)          |
    |          ^                               ^                  |
    |          |              TCP              |                  |
    |          v                               v                  |
    |  Node 4 (Port 9004) <---TCP---> Node 3 (Port 9003)          |
    |          ^                                                  |
    |          +------------TCP-----> Node 5 (Port 9005) [KING]   |
    +-------------------------------------------------------------+
       (Real election messages travel directly node-to-node)
```

**Key Architectural Rule**: Election messages travel strictly **node-to-node** directly over TCP sockets. The gateway only supervises processes, listens to telemetry events, and delivers user control commands.

---

## ⚡ Quick Start (One Command)

### Prerequisites
- Python 3.11+
- Node.js 20+ (for building the frontend if desired; pre-built production assets are included in `frontend/dist`)

### Run the Kingdom
```bash
python run.py
```
This automatically:
1. Initializes SQLite persistence (`sovereign.db`).
2. Spawns 5 independent Python node processes (`backend.node.node`).
3. Launches the FastAPI gateway and WebSocket telemetry hub on `http://127.0.0.1:8000`.
4. Automatically triggers the initial coronation.
5. Opens your default web browser to the interactive 3D dashboard!

---

## 🧪 Automated Test Suite

Run the full backend test suite covering unit tests and cluster integration tests:

```bash
python -m pytest backend/tests/ -v
```

### Test Coverage:
- `test_lamport.py`: Lamport clock ticks, monotonic updates, and causal ordering across nodes.
- `test_heartbeat.py`: Failure detection timeouts, periodic heartbeats, and ACK recording.
- `test_bully.py`: Highest ID immediate coronation, OK timeout when higher nodes are unresponsive, and bully takeover.
- `test_ring.py`: Circular successor ordering, token traversal, dead-node skipping, and winner announcement.
- `test_integration.py`: End-to-end 5-node cluster over real TCP sockets:
  1. Bully election electing Node 5.
  2. Assassinating Node 5 and verifying failover to Node 4.
  3. Reviving Node 5 and asserting Bully takeover.
  4. Switching cluster to Ring mode, assassinating Node 5, and verifying Ring election of Node 4.
- `test_gateway.py`: REST endpoints, cluster state, algorithm switching, and CSV/JSON export.

---

## 🎮 Interactive Controls & Keyboard Shortcuts

| Shortcut | Action | Description |
| :---: | :--- | :--- |
| **`K`** | **Assassinate King** | Strikes lightning on current sovereign and triggers failover |
| **`E`** | **Hold Election** | Initiates an election from a live node |
| **`C`** | **Toggle Chaos** | Starts/stops random strikes and revivals |
| **`1`** | **Kingdom View** | Switches to main 3D dashboard |
| **`2`** | **Analytics View** | Opens benchmark and complexity charts |
| **`3`** | **Replay View** | Opens the timeline scrubber |
| **`4`** | **Viva Guide** | Displays examiner viva questions and answers |

---

## 📂 Project Structure

```text
D:\Aanaya\
├── run.py                    # Master launcher script (python run.py)
├── README.md                 # Project documentation & viva guide
├── sovereign.db              # SQLite persistence (elections & events)
├── backend/
│   ├── protocol.py           # Message schemas, LamportClock, Enums
│   ├── node/
│   │   ├── node.py           # Independent OS process & TCP server
│   │   ├── bully.py          # Bully algorithm implementation
│   │   ├── ring.py           # Ring algorithm implementation
│   │   └── heartbeat.py      # Heartbeat failure detector
│   ├── gateway/
│   │   ├── app.py            # FastAPI REST API & WebSocket server
│   │   ├── supervisor.py     # Process supervisor & dynamic scaler
│   │   ├── telemetry.py      # Telemetry hub & live broadcaster
│   │   ├── models.py         # SQLModel database schemas
│   │   └── database.py       # SQLite connection setup
│   └── tests/
│       ├── test_lamport.py
│       ├── test_heartbeat.py
│       ├── test_bully.py
│       ├── test_ring.py
│       ├── test_integration.py
│       └── test_gateway.py
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── src/
    │   ├── scene/            # 3D R3F components (Island, Castle, Crown, Orbs, Camera)
    │   ├── ui/               # Panels (Header, NodeList, Logs, Dock, Analytics, Replay)
    │   ├── store/            # Zustand state management
    │   └── lib/              # API client, WebSocket hook, types
    └── dist/                 # Production-built bundle served by Gateway
```

---

## 🎓 Viva Questions & Answers

### 1. Why is Bully $O(N^2)$ in the worst case and Ring $O(N)$?
In Bully, if the lowest ID detects failure, it messages all higher nodes ($N-1$). Each higher node messages all its higher nodes:
$$\sum_{i=1}^{N-1} i = \frac{N(N-1)}{2} = O(N^2)$$
In Ring mode, the token visits each alive node exactly once during election and once during coordinator announcement: roughly $2N = O(N)$ messages.

### 2. How do you resolve simultaneous elections?
Each election carries an `election_id` containing the initiator's ID. When a node receives an election token/message while already participating in an election, it compares initiator IDs: the election with the higher initiator ID takes precedence, and the lower one is dropped.

### 3. What is the purpose of the Lamport clock?
Physical wall-clock timestamps drift between independent processes and machines. Lamport logical clocks ensure that if event $A \to B$ (causally precedes), then $L(A) < L(B)$. This enables unambiguous causal replay across distributed nodes.

### 4. Which algorithm would you use in production?
Neither Bully nor Ring is typically used in modern production clusters due to vulnerability to network partitions. Production systems use consensus algorithms like **Raft** (etcd, Consul) or **Multi-Paxos** (ZooKeeper Zab) that rely on majority quorums ($(N/2)+1$) to prevent split-brain.
