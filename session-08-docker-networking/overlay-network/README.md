# Docker Overlay Network (Task 4 research)

**Student:** Vivek Singh Solanki | **Roll number:** 24bcs10338
**Session:** 08 - Docker Networking
**Task:** Research the overlay network driver: what it is, when to use it, and how it works across multiple Docker hosts

The default `bridge` network only connects containers on one machine. As soon as an application is spread across several Docker hosts (for scale or high availability), containers on different machines need a way to talk to each other by name and IP as if they were on the same LAN. Docker's answer is the **overlay** network driver.

## What is an overlay network?

An overlay network is a **virtual Layer 2 network that spans multiple Docker hosts**. Containers attached to the same overlay get IP addresses from one subnet (for example `10.0.9.0/24`) and can reach each other directly, even though the hosts themselves sit on a separate physical network (the "underlay", e.g. `192.168.1.0/24`).

The virtualisation is done with **VXLAN** (Virtual Extensible LAN, RFC 7348). Each Ethernet frame leaving a container is wrapped inside a UDP packet, sent across the physical network to the correct host, and unwrapped there. From the container's point of view it is a flat network; from the physical network's point of view it is only UDP traffic between hosts.

Overlay networks are built into Docker Engine but require **Swarm mode** (or an external key-value store in very old setups) because the hosts need a shared control plane to agree on which container IP lives on which host.

## Use cases

- **Docker Swarm services** - every Swarm service that needs networking is attached to an overlay; replicas can land on any node and still reach each other.
- **Multi-host container communication** - a web container on host A talks to a database container on host B using its container name.
- **Service discovery across nodes** - Docker's embedded DNS (127.0.0.11) resolves service and container names on the overlay regardless of which node they run on, and a service name resolves to a virtual IP that load-balances across replicas.
- **Isolating multi-host applications** - each application stack gets its own overlay; containers on different overlays cannot see each other, the same isolation model as user-defined bridges but cluster-wide.
- **Standalone containers on a Swarm** - with `--attachable`, plain `docker run` containers (not only services) can join an overlay for debugging or legacy components.

## How it works across multiple Docker hosts

### Data plane: VXLAN encapsulation

1. Container `web` (10.0.9.3 on host A) sends a packet to `db` (10.0.9.4 on host B).
2. The packet reaches the overlay's bridge inside a dedicated network namespace on host A.
3. The VXLAN interface looks up the destination MAC/IP in its forwarding table (populated by the control plane) and finds that 10.0.9.4 is behind host B (192.168.1.20).
4. The original frame is encapsulated in a VXLAN header + **UDP port 4789** packet with source 192.168.1.10 and destination 192.168.1.20 and sent over the physical NIC.
5. Host B receives the UDP packet, strips the VXLAN header and delivers the inner frame to container `db`.

Each overlay network has its own VXLAN Network Identifier (VNI), so frames from different overlays never mix even though they share UDP 4789.

### Control plane: Swarm gossip

The mapping "container IP/MAC -> host" has to be distributed to every node. Swarm does this with:

- The **Raft-backed manager store** (TCP 2377) for network definitions, IPAM allocations and service state.
- A **gossip protocol** between all nodes (TCP and UDP 7946) that propagates endpoint entries so each node can fill its VXLAN forwarding tables without flooding.

Required ports between all Swarm nodes:

| Port | Protocol | Purpose |
|---|---|---|
| 2377 | TCP | Cluster management (manager nodes), `docker swarm join` |
| 7946 | TCP + UDP | Node discovery and gossip for overlay control plane |
| 4789 | UDP | VXLAN data plane (container-to-container traffic) |
| 50 | ESP (IP protocol) | Only when overlay encryption is enabled |

### Diagram: two hosts, one overlay

```
            Overlay network "my-overlay"  10.0.9.0/24  (VNI 4097)
  . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
  .                                                                   .
  .   +-------------+   +-------------+        +-------------+        .
  .   | web         |   | api         |        | db          |        .
  .   | 10.0.9.3    |   | 10.0.9.5    |        | 10.0.9.4    |        .
  .   +------+------+   +------+------+        +------+------+        .
  . . . . . .|. . . . . . . . .|. . . . . . . . . . . |. . . . . . . .
             |                 |                      |
      +------+-----------------+------+        +------+-------------+
      | br0 (overlay bridge)          |        | br0 (overlay bridge)|
      | vxlan0  VNI 4097, UDP 4789    |        | vxlan0  VNI 4097    |
      +-------------------------------+        +---------------------+
      | Host A   eth0 192.168.1.10    |        | Host B  eth0 192.168.1.20 |
      +-------------------------------+        +---------------------------+
                      |                                    |
                      |   [ UDP 4789 ] outer IP 192.168.1.10 -> 192.168.1.20
                      |   [ VXLAN hdr VNI 4097 ]
                      |   [ inner frame 10.0.9.3 -> 10.0.9.4 ]
                      +-----------( physical network )-----------+
```

The physical switch only sees traffic between 192.168.1.10 and 192.168.1.20 on UDP 4789. The container addresses (10.0.9.x) exist only inside the tunnel.

## The ingress overlay and the routing mesh

When Swarm is initialised, Docker automatically creates a special overlay network named **`ingress`**. It carries external traffic for published service ports and implements the **routing mesh**:

- A service published with `--publish 8080:80` listens on port 8080 on **every node** in the Swarm, even nodes with no replica of that service.
- A request arriving on any node is forwarded over the `ingress` overlay (using IPVS load balancing) to a healthy replica wherever it runs.
- This lets an external load balancer point at any or all nodes without knowing where tasks are scheduled.

`--publish mode=host` bypasses the mesh and exposes the port only on nodes that run a task. The `ingress` network cannot be used for container-to-container traffic; application networks should always be separate overlays.

```
   client -> node3:8080 (no replica here) --ingress overlay--> node1:80 (replica) or node2:80 (replica)
```

## Encrypted overlay

By default the VXLAN payload crosses the network in clear text. Adding `--opt encrypted` at creation time makes Docker set up IPsec tunnels (ESP) between every pair of nodes that host tasks on that network, with keys rotated automatically every 12 hours by the managers.

```bash
docker network create --driver overlay --opt encrypted --attachable secure-net
```

Trade-offs: encryption costs CPU on every packet, requires IP protocol 50 (ESP) to be open between nodes, and is not supported on Windows nodes. Swarm's management traffic (2377, 7946) is already TLS-encrypted regardless of this option.

## Commands

```bash
# on the first host: create the Swarm (this also creates the ingress overlay and docker_gwbridge)
docker swarm init --advertise-addr 192.168.1.10
# prints a join token; on the other hosts:
docker swarm join --token SWMTKN-1-xxxx 192.168.1.10:2377
docker node ls                                        # from a manager

# create an application overlay (attachable so plain containers can join too)
docker network create -d overlay --attachable --subnet 10.0.9.0/24 my-overlay
docker network ls                                     # SCOPE column shows "swarm"

# run services on it
docker service create --name db  --network my-overlay postgres:16
docker service create --name web --network my-overlay --replicas 3 --publish 8080:80 nginx:1.27
docker service ls
docker service ps web                                 # shows which node each replica landed on

# attach a standalone container for debugging
docker run -it --rm --network my-overlay nicolaka/netshoot
#   inside: nslookup db ; ping db ; curl web

# inspect: shows subnet, VXLAN id, peers and the containers from every node
docker network inspect my-overlay
docker network inspect my-overlay --format '{{json .Peers}}'
docker network inspect ingress --format '{{.Options}}'    # com.docker.network.driver.overlay.vxlanid_list

# clean up
docker service rm web db
docker network rm my-overlay
docker swarm leave --force
```

Note: an overlay network only appears on a worker node once a task that uses it is scheduled there; `docker network ls` on an idle worker will not list it yet.

## Overlay vs bridge vs host vs macvlan

| Driver | Scope | Container addressing | Isolation | Performance | Typical use |
|---|---|---|---|---|---|
| `bridge` (default or user-defined) | Single host | Private subnet (172.17.0.0/16 etc.) behind NAT | Per network; user-defined bridges get DNS by name | Good; one NAT hop | Local development, Compose stacks on one machine |
| `host` | Single host | Shares the host's IP and port space | None; container ports collide with host ports | Best (no NAT, no veth) | High-throughput daemons, monitoring agents |
| `overlay` | Multi-host (Swarm) | Cluster-wide subnet, VXLAN tunnels | Per overlay, across all nodes; optional IPsec | VXLAN adds ~50 bytes per packet and some CPU | Swarm services, multi-host applications |
| `macvlan` | Single host (per NIC) | Each container gets its own MAC and an IP on the physical LAN | Visible on the LAN like a real device | Near native | Legacy apps that must be on the physical network, no NAT |
| `ipvlan` | Single host | Shares host MAC, own IP (L2) or routed (L3) | Similar to macvlan | Near native | When the switch limits MACs per port or in cloud VMs |
| `none` | Single host | Only loopback | Full | n/a | Security sandboxes, batch jobs with no networking |

Kubernetes note: Kubernetes does not use Docker overlay networks. CNI plugins such as Flannel (VXLAN backend) and Calico (VXLAN or IPIP) solve the same multi-host problem with the same encapsulation idea, which is why understanding VXLAN here transfers directly.

## Limitations

- **Requires Swarm mode.** Without `docker swarm init` the overlay driver is unavailable; it is not a drop-in for Compose on several machines.
- **MTU overhead.** VXLAN adds 50 bytes; if the physical network MTU is 1500 the overlay MTU drops to 1450. Mismatched MTUs cause fragmented or dropped large packets.
- **Firewall dependencies.** TCP 2377, TCP/UDP 7946 and UDP 4789 (plus ESP for encryption) must be open between all nodes; cloud security groups frequently block these by default.
- **Encryption is optional and costly.** Clear-text by default; `--opt encrypted` adds CPU load and does not work with Windows containers.
- **Performance.** Encapsulation, gossip and IPVS add latency compared with `host` or `macvlan`; overlay is rarely the right choice for very high packet rates.
- **No multicast / broadcast.** Applications relying on L2 broadcast discovery do not work across the overlay.
- **Troubleshooting is harder.** Traffic is hidden inside tunnels, so debugging needs `tcpdump udp port 4789` on the hosts or `nsenter` into the overlay namespace.
- **Scale limits.** Docker recommends keeping each overlay to a few hundred endpoints and the whole Swarm to a manageable number of nodes; very large clusters usually move to Kubernetes.

## Key takeaways

1. Overlay = one virtual L2 network across many hosts, built on VXLAN over UDP 4789.
2. Swarm managers (TCP 2377) and the gossip protocol (7946) distribute the "which IP is on which host" table.
3. The automatically created `ingress` overlay provides the routing mesh for published ports.
4. Use `--attachable` for standalone containers, `--opt encrypted` when traffic crosses untrusted networks.
5. Bridge for one host, overlay for many hosts, host/macvlan when raw performance or LAN presence matters more than isolation.

## References

- Docker overlay network driver: https://docs.docker.com/engine/network/drivers/overlay/
- Networking with overlay networks (tutorial): https://docs.docker.com/engine/network/tutorials/overlay/
- Docker network drivers overview: https://docs.docker.com/engine/network/drivers/
- Swarm mode routing mesh: https://docs.docker.com/engine/swarm/ingress/
- Swarm networking and ports: https://docs.docker.com/engine/swarm/networking/
- `docker network create` reference: https://docs.docker.com/reference/cli/docker/network/create/
- VXLAN specification, RFC 7348: https://datatracker.ietf.org/doc/html/rfc7348
