# 👑 Sovereign: Complete System Manual & Viva Guide
### *An Easy, Detailed Guide to Every Function, Button, and Algorithm for PDF Export*

---

## 1. Executive Summary: What is Sovereign?

**Sovereign** is an interactive 3D simulation of a **Distributed Computing System** disguised as a fantasy kingdom of floating sky castles.

In the real world, distributed systems power companies like **Google, Amazon, Netflix, and online banks**. Instead of running on a single computer, these systems distribute their work across dozens, hundreds, or thousands of independent server computers (called **Nodes**).

To prevent chaos (e.g., two computers modifying the same database record at the same moment), **one node must always be elected the "Leader" (or "Coordinator")**. 

* **The Challenge**: If the leader crashes, loses power, or gets disconnected, the remaining computers must detect the death and automatically elect a new leader **without any human intervention**.
* **The Solution**: Distributed Leader Election Algorithms. Sovereign visually demonstrates the two most famous textbook algorithms: the **Bully Algorithm** and the **Ring Algorithm**.

---

## 2. The Kingdom Metaphor: How to Visualize It

| Visual in Sovereign | What It Represents in Real Distributed Computing |
| :--- | :--- |
| **Floating Island** | The local network / cluster boundary hosting all machines. |
| **Each Castle** | An **independent computer program (OS process)** running on its own local network port (e.g., 9001, 9002, 9003, etc.). |
| **Castle Numbers (1 to 5)** | The unique **Process ID (Node ID)**. Higher IDs represent higher priority. |
| **The Sovereign (King)** | The **Elected Leader / Coordinator** node currently in charge. |
| **The Golden Crown** | The **Coordinator Status**. Only one living node can wear it at any time. |
| **Floating Sky Crown** | The **Vacant State**. When a king dies, the crown floats to the sky `[0, 7.2, 0]` until a new leader is elected. |
| **Glowing Flying Orbs** | Real **TCP network packets** traveling between computer processes over local sockets. |
| **Tilted Broken Castle** | A **Dead / Crashed Process** that cannot send or receive messages. |
| **Blinking Blue Ring** | A node in the **Electing** state, actively seeking votes. |

---

## 3. How the Castles Know When the King Dies: The Heartbeat

Castles cannot "see" each other; they communicate strictly over network sockets.

```text
[Follower Castle]  ─── "Are you alive?" (Heartbeat Ping every 1.0s) ───►  [King Castle]
[Follower Castle]  ◄── "Yes, I am alive!" (Heartbeat ACK) ──────────────  [King Castle]
```

1. **Periodic Ping**: Every **1.0 second**, every living follower castle sends a tiny TCP packet to the King: *"Are you alive?"*
2. **Immediate Reply**: As long as the King process is healthy, it immediately replies: *"Yes, I am alive!"*
3. **Failure Detection**: If the King crashes (lightning strike or assassinated):
   * The King stops replying.
   * Followers wait for **2.2 seconds** (the failure timeout).
   * Once 2.2 seconds pass with silence, the follower declares: *"The King is dead!"*
4. **Crown Ascends**: The golden crown lifts off the dead castle, hovers high in the sky, and surviving castles initiate an election according to the active algorithm.

---

## 4. Algorithm 1: The Bully Algorithm (Garcia-Molina, 1982)

### The Core Idea: *"The biggest ID always bullies the smaller IDs."*
In this algorithm, rank is determined strictly by process ID. Castle 5 outranks Castle 4, Castle 4 outranks Castle 3, etc.

```text
[King Node 5 Dies]
       │
       ▼
[Node 1 notices timeout]
       │
       ▼
[Node 1 broadcasts ELECTION to Nodes 2, 3, 4, 5]
       │
       ▼
[Nodes 2, 3, 4 reply 'OK' to Node 1: "Quiet, we are higher!"]
       │
       ▼
[Node 4 broadcasts ELECTION to Node 5]
       │
       ▼
[Node 5 is dead (No answer after 1.0s)]
       │
       ▼
[Node 4 broadcasts COORDINATOR: "I am your new Sovereign!"]
       │
       ▼
[Crown swoops down to Node 4]
```

### Step-by-Step Execution:
1. **Initiation**: Any node that notices the leader died sends an `ELECTION` message to **all nodes with higher IDs**.
2. **The "OK" Answer**: If any higher node is alive, it replies `OK` (*"I have a higher ID than you, stand down, I'll take over"*). The lower node's job is done; it waits for the higher node to become coordinator.
3. **Ascension**: The higher node now sends `ELECTION` to nodes higher than itself. If no higher node answers within the timeout (**1.0 second**), this node knows it is the highest living node in the entire network!
4. **Victory Announcement**: It broadcasts a `COORDINATOR` message to all living nodes: *"I am the new Leader."*
5. **Bully Takeover (Revival Rule)**: If Castle 5 was dead and suddenly revives (comes back to life), it does not politely ask for permission. Because $5 > 4$, it immediately bullies Castle 4, deposes it, and takes back the crown!

> **Mathematical Complexity**:
> * **Worst-case Message Traffic**: $O(N^2)$ — If the lowest node detects failure, everyone messages everyone higher: $\frac{N(N-1)}{2}$ messages. Very loud and chatty, but very fast.

---

## 5. Algorithm 2: The Ring Algorithm (Chang & Roberts, 1979)

### The Core Idea: *"An orderly relay race in a circle."*
Instead of broadcasting to everyone at once, all castles are logically arranged in a circle:
$$\text{Castle 1} \longrightarrow \text{Castle 2} \longrightarrow \text{Castle 3} \longrightarrow \text{Castle 4} \longrightarrow \text{Castle 5} \longrightarrow \text{Castle 1}$$

```text
Castle 1 (adds [1])
       │
       ▼
Castle 2 (adds [1, 2])
       │
       ▼
Castle 3 (adds [1, 2, 3])
       │
       ▼
Castle 4 (adds [1, 2, 3, 4])
       │ (skips dead Castle 5)
       ▼
Returns to Castle 1!
Castle 1 evaluates: Winner = Max(1,2,3,4) = 4
```

### Step-by-Step Execution:
1. **Initiation**: When a node detects leader failure, it creates an **Election Token** containing an "active list" with its own ID: `[1]`.
2. **Sequential Forwarding**: It forwards the token clockwise to its alive successor (Castle 2).
3. **Appending**: Castle 2 adds its own ID: `[1, 2]`, and forwards to Castle 3. Castle 3 adds its ID: `[1, 2, 3]`, and forwards to Castle 4.
4. **Dead-Node Skipping**: Castle 4 tries to contact Castle 5. Because Castle 5 is dead (TCP connection fails), Castle 4 automatically **skips** Castle 5 and forwards directly to Castle 1!
5. **Full Circuit Completion**: When the token returns to the initiator (Castle 1), Castle 1 inspects the list: `[1, 2, 3, 4]`. The highest living number is **4**.
6. **Coordinator Token**: Castle 1 sends a `RING_COORDINATOR` token around the circle: *"Castle 4 is the new Sovereign."* Every node updates its leader, and the crown lands on Castle 4.

> **Mathematical Complexity**:
> * **Message Traffic**: $O(N)$ — The token visits each node once during election and once during announcement ($2N$ messages). Extremely neat, polite, and low-traffic.

---

## 6. Every Button & Control Explained in Detail

### Bottom Control Dock (Main Controls)

| Button / Icon | Plain-English Explanation | What Happens Behind the Scenes |
| :--- | :--- | :--- |
| **💀 Assassinate King** | Instantly strikes down the current Sovereign with lightning. | Sends `POST /api/cluster/assassinate` to the gateway. The leader process is killed, its status transitions to `DEAD`, the crown lifts to `[0, 7.2, 0]`, and followers trigger an election. |
| **🗳️ Hold Election** | Manually forces an election to run right now. | Sends `POST /api/cluster/election/start`. Surviving nodes trigger an election and exchange glowing orbs even if no node is dead. |
| **⚡ Chaos Mode: ON / OFF** | Unleashes an unpredictable storm of random lightning and revivals. | A background chaos task strikes random living nodes with lightning and revives dead nodes every 4–7 seconds. Proves the cluster can survive constant chaos. |
| **🏰 Nodes Slider (3 to 9)** | Dynamically adds or removes castles from the kingdom. | Sends `POST /api/cluster/scale`. When scaled up to 7, new Python processes for Nodes 6 and 7 are spawned live and announce membership over TCP. When scaled down, excess processes are terminated gracefully. |
| **🎚️ Sliders Icon** | Expands the **Network Fault Injection** toolbar. | Opens controls for simulated Latency and Packet Drops. |
| **⏱️ Latency Slider (0–1000ms)** | Simulates bad network cables or slow satellite internet. | Tells node TCP servers to sleep for $X$ milliseconds before reading packets. Glowing orbs travel visibly slower across the sky. |
| **📦 Drop Rate Slider (0–50%)** | Simulates lost network packets (flaky Wi-Fi). | Nodes randomly discard $X\%$ of incoming messages to test algorithm recovery under packet loss. |

---

### Top Header & Navigation Bar

| Control | Plain-English Explanation |
| :--- | :--- |
| **Algorithm Selector (BULLY / RING)** | Instantly switches the cluster's active election algorithm. Sends a control message to all running Python processes to swap their state machine. |
| **☀️ / 🌙 Sun & Moon Toggle** | Toggles between **Day Mode** (bright sky, high-contrast solid black castle numbers with white outline halos) and **Night Mode** (dark cinematic sky, illuminated towers, glowing runes). |
| **Heartbeat Toggle (WiFi icon)** | Turns on/off visual rendering of the periodic blue heartbeat pings flying between followers and the King (off by default to keep the 3D scene clean). |
| **Tab 1: 🏰 Kingdom** | Switches back to the main interactive 3D floating island view. |
| **Tab 2: 📊 Analytics** | Opens the Performance Benchmarking and Mathematical Comparison modal. |
| **Tab 3: ⏱️ Replay** | Opens the Lamport Causal Order Timeline Scrubber modal. |
| **Sovereign Status Badge** | Displays either `👑 Sovereign: Node X` (with gold glow) or `🔴 Crown Vacant (Electing...)` with a pulsing red alert if a leader is currently dead. |

---

### Left Drawer: 🏰 Castles Panel
*Click the **🏰 Castles** floating pill on the left to open:*
* **Castle Cards (1 to N)**: Displays the real-time status of each individual computer process:
  * `LEADER`: Crowned Sovereign.
  * `ALIVE`: Normal healthy follower.
  * `ELECTING`: Actively broadcasting or processing election tokens.
  * `DEAD`: Process has crashed (tilted castle, red embers).
* **Port Display**: Shows the real local TCP port (e.g., `Port 9001`, `Port 9005`).
* **💀 Kill Button**: Lets you assassinate any specific castle of your choice with one click.
* **❤️ Revive Button**: Magically brings a dead castle back to life. In Bully mode, revives trigger an immediate takeover challenge!

---

### Right Drawer: 📜 Live Logs Panel
*Click the **📜 Live Logs** floating pill on the right to open:*
* **Live Network Stream**: Shows the actual TCP packets flying across your operating system in real-time.
* **Packet Details**: Shows Timestamp (to the millisecond), Lamport logical clock tick, Sender Castle, Receiver Castle, and Packet Type.
* **Filter Tabs**: Click `ELECTION`, `OK`, `COORDINATOR`, or `HEARTBEAT` to isolate and inspect specific message types.
* **Trash Icon**: Clears the on-screen log history.

---

## 7. What the "Analytics" Feature is Doing (Tab 2)

When you click **Analytics** (or press key `2`), you enter the **Distributed Systems Science Laboratory**.

### Why do we need this?
To provide undeniable scientific proof to faculty and examiners that your algorithms match their theoretical complexity!

### The Charts Explained:
1. **Message Complexity Chart (Total Messages Sent)**:
   * Compares the number of network messages required to complete an election as the number of nodes increases (3, 5, 7, 9 nodes).
   * **Bully (Orange Bar)**: Grows quadratically ($O(N^2)$). For 9 nodes, the bar shoots high into the air because everyone messages everyone higher.
   * **Ring (Gold Bar)**: Grows linearly ($O(N)$). The bar stays low and flat because the token simply circulates around the circle twice ($2N$).
2. **Election Duration Chart (Milliseconds to Elect)**:
   * Shows how many milliseconds elapsed between the King's death and the coronation.
   * Bully is usually faster in pure time because messages are sent in parallel; Ring takes slightly longer because tokens pass sequentially.
3. **The "Run Benchmark" Button**:
   * Automatically executes **10 automated election rounds** across different cluster sizes, records the network metrics into SQLite, and updates the graphs with empirical averages!
4. **CSV / JSON Export**:
   * Click **Export CSV** to download the raw benchmark numbers for your project report or presentation slides.

---

## 8. What the "Replay" Feature is Doing (Tab 3)

When you click **Replay** (or press key `3`), you open a **Causal Time-Machine**.

### The Problem in Distributed Systems:
Computers have independent physical quartz clocks that drift by milliseconds or seconds. You cannot trust physical time to know which computer acted first.

### The Solution: Lamport Logical Clocks (Leslie Lamport, 1978)
Every castle maintains a simple integer counter ($1, 2, 3 \dots$). Whenever a message is sent or received, the counter ticks forward monotonically. If Event A caused Event B, then:
$$L(A) < L(B)$$

### How to Use the Replay Scrubber:
* **Timeline Slider**: Drag the slider backward to rewind to past events.
* **Step Controls (Previous / Next)**: Step through history message-by-message.
* **Causal Demonstration**: Show your faculty examiner:
  1. *"At Lamport Tick 12, Node 5 was assassinated."*
  2. *"At Lamport Tick 13, Node 1 noticed silence and initiated an election."*
  3. *"At Lamport Tick 15, Node 4 replied OK and took over."*
  4. *"At Lamport Tick 18, Node 4 announced victory."*

---

## 9. Top 7 Viva Presentation Questions & Model Answers

### Q1: What is the main purpose of your project?
> *"Sovereign is a real distributed system with independent OS processes communicating over raw TCP sockets. It visually demonstrates how distributed nodes detect leader failure via periodic heartbeats and elect a new coordinator using the classic Bully and Ring algorithms."*

### Q2: Why is Bully $O(N^2)$ while Ring is $O(N)$?
> *"In the Bully algorithm, every node messages all higher-ranked nodes simultaneously, leading to $\sum i = \frac{N(N-1)}{2} = O(N^2)$ messages in the worst case. In the Ring algorithm, the token only visits each alive node once during the election and once during coordinator announcement, requiring roughly $2N = O(N)$ messages."*

### Q3: Why is it called the 'Bully' algorithm?
> *"Because higher process IDs have absolute authority over lower IDs. Any alive node with a higher ID bullies lower nodes into submission by replying 'OK' and taking over the election."*

### Q4: How does the Ring algorithm handle node crashes?
> *"Nodes maintain circular successor ordering. If an immediate neighbor's TCP socket is closed or unreachable, the sender automatically skips the dead node and connects to the next living successor in the ring."*

### Q5: What is the role of Lamport Clocks?
> *"Physical wall clocks drift between independent computers. Lamport logical clocks assign a monotonically increasing integer timestamp to every send and receive event, guaranteeing unambiguous causal ordering for event replay and auditing."*

### Q6: What happens when the King crashes in your 3D visualization?
> *"Followers detect the missing heartbeat within 2.2 seconds. The golden crown immediately detaches from the dead castle, floats to the center sky above the island, and remains vacant until an election declares a new living sovereign."*

### Q7: Are Bully and Ring used in modern cloud databases like Google Spanner or AWS DynamoDB?
> *"Rarely today, because neither handles network partitions (split-brain) well. Modern production databases use quorum consensus algorithms like **Raft** or **Multi-Paxos**, which require majority agreement ($(N/2)+1$) before electing a leader."*
