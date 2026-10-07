# Kubernetes Volumes

**Student:** Vivek Singh Solanki | **Roll number:** 24bcs10338
**Session:** 13 - Kubernetes Storage, HPA and Probes
**Topic:** Volumes, PersistentVolumes, PersistentVolumeClaims, StorageClasses and dynamic provisioning

Containers are ephemeral. When a container restarts, everything written to its writable layer is gone. Kubernetes solves this with the Volume abstraction: a directory that is mounted into one or more containers of a Pod and whose lifetime and backing storage depend on the volume *type*. This document summarizes the volume types I worked with in this session, from the simplest (emptyDir) up to fully dynamic, cluster-managed storage.

## Quick comparison

| Volume type | Scope / lifetime | Survives Pod restart? | Survives Pod deletion? | Typical use |
|---|---|---|---|---|
| `emptyDir` | Pod | Yes (container restart) | No | Scratch space, cache, sharing files between containers in one Pod |
| `hostPath` | Node | Yes | Yes (as long as the same node is used) | Dev/test, node agents (log collectors, CNI), single-node clusters like minikube |
| `PersistentVolume` + `PersistentVolumeClaim` | Cluster | Yes | Yes (depends on reclaim policy) | Databases, user uploads, anything stateful |
| `StorageClass` (dynamic) | Cluster | Yes | Yes (depends on reclaim policy) | Production stateful workloads, cloud block storage (EBS, PD, Azure Disk) |

## 1. emptyDir

An `emptyDir` volume is created when a Pod is scheduled to a node and starts out empty. All containers in the Pod can mount it (at the same or different paths), so it is the standard way to share files between a main container and a sidecar. The data survives container crashes and restarts, but it is deleted permanently when the Pod is removed from the node.

Key points:

- Lifecycle is tied to the **Pod**, not the container.
- Default medium is the node's disk. `medium: Memory` backs it with tmpfs (RAM): faster, but counts against the container memory limit and is lost on node reboot.
- `sizeLimit` can cap how much the volume can grow; exceeding it evicts the Pod.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: emptydir-demo
spec:
  containers:
    - name: writer
      image: busybox:1.36
      command: ["sh", "-c", "while true; do date >> /data/log.txt; sleep 5; done"]
      volumeMounts:
        - name: shared
          mountPath: /data
    - name: reader
      image: busybox:1.36
      command: ["sh", "-c", "tail -f /shared/log.txt"]
      volumeMounts:
        - name: shared
          mountPath: /shared
  volumes:
    - name: shared
      emptyDir:
        medium: Memory      # omit this line to use node disk
        sizeLimit: 64Mi
```

Commands to try:

```bash
kubectl apply -f emptydir-demo.yaml
kubectl logs emptydir-demo -c reader -f          # reader sees what writer wrote
kubectl exec emptydir-demo -c writer -- df -h /data   # shows tmpfs when medium: Memory
kubectl delete pod emptydir-demo                 # the data is gone with the Pod
```

## 2. hostPath

A `hostPath` volume mounts a file or directory from the **node's filesystem** into the Pod. The data lives on the node, so it survives Pod deletion, but a Pod rescheduled onto a different node sees a different (probably empty) directory.

The `type` field controls validation:

| type | Behaviour |
|---|---|
| `""` (empty, default) | No checks are performed |
| `DirectoryOrCreate` | Create the directory (mode 0755) if it does not exist |
| `Directory` | Must already exist as a directory |
| `FileOrCreate` | Create an empty file if it does not exist |
| `File` | Must already exist as a file |
| `Socket` / `CharDevice` / `BlockDevice` | Must exist as that kind of object |

Security warning: hostPath lets a Pod read and write the host's disk. A container mounting `/` or `/var/run/docker.sock` can escape to the node. Most admission policies (Pod Security Standards `baseline` and `restricted`) block hostPath entirely. Use it only for single-node development clusters or trusted node-level agents such as log shippers.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: hostpath-demo
spec:
  containers:
    - name: app
      image: nginx:1.27
      volumeMounts:
        - name: html
          mountPath: /usr/share/nginx/html
  volumes:
    - name: html
      hostPath:
        path: /mnt/data/html
        type: DirectoryOrCreate
```

Commands to try (minikube):

```bash
kubectl apply -f hostpath-demo.yaml
minikube ssh -- "echo '<h1>from the node</h1>' | sudo tee /mnt/data/html/index.html"
kubectl exec hostpath-demo -- cat /usr/share/nginx/html/index.html
kubectl delete pod hostpath-demo && minikube ssh -- ls /mnt/data/html   # file still on node
```

## 3. PersistentVolume (PV)

A `PersistentVolume` is a cluster-level resource that represents a piece of real storage: an NFS export, a cloud disk, a local disk on a node, or (for learning) a hostPath. It is created either by an administrator (static provisioning) or automatically by a StorageClass (dynamic provisioning). PVs are not namespaced.

Important fields:

- `capacity.storage` - how big the volume is.
- `accessModes` - how the volume can be mounted:

| Mode | Short | Meaning |
|---|---|---|
| `ReadWriteOnce` | RWO | Read-write by a single **node** (multiple Pods on that node can share it) |
| `ReadOnlyMany` | ROX | Read-only by many nodes |
| `ReadWriteMany` | RWX | Read-write by many nodes (NFS, EFS, CephFS; not plain EBS) |
| `ReadWriteOncePod` | RWOP | Read-write by exactly one **Pod** in the whole cluster (CSI only, GA since v1.29) |

- `persistentVolumeReclaimPolicy` - what happens when the claim is deleted:

| Policy | Behaviour |
|---|---|
| `Retain` | PV stays, status becomes `Released`; data is kept, admin must clean up and delete the PV manually before it can be reused |
| `Delete` | PV and the underlying storage (cloud disk) are deleted. Default for dynamically provisioned volumes |
| `Recycle` | Deprecated. Ran `rm -rf` on the volume and made it `Available` again; only old NFS/hostPath plugins supported it |

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: pv-manual-1gi
spec:
  capacity:
    storage: 1Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: manual          # a label used to match a PVC; does not need a real StorageClass object
  hostPath:
    path: /mnt/data/pv1
    type: DirectoryOrCreate
```

On multi-node clusters a `local` volume (with `nodeAffinity` pinning it to a node) is the correct replacement for a hostPath-backed PV, because the scheduler then knows which node holds the data.

Commands to try:

```bash
kubectl apply -f pv-manual.yaml
kubectl get pv                                   # STATUS should be Available
kubectl describe pv pv-manual-1gi
```

## 4. PersistentVolumeClaim (PVC)

A `PersistentVolumeClaim` is a namespaced request for storage made by a user or application: "I need at least 500Mi, ReadWriteOnce, from class `manual`". The control plane finds a PV that satisfies the request and **binds** the two; a bound PV can only ever be used by that one PVC. The Pod then references the PVC, not the PV, so application manifests stay independent of the physical storage.

Binding rules: the PV must have the same `storageClassName`, an access mode that covers the request, and capacity greater than or equal to the request. If nothing matches, the PVC stays `Pending`.

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: pvc-manual
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: manual
  resources:
    requests:
      storage: 500Mi
---
apiVersion: v1
kind: Pod
metadata:
  name: pvc-demo
spec:
  containers:
    - name: app
      image: busybox:1.36
      command: ["sh", "-c", "echo hello > /data/hello.txt && sleep 3600"]
      volumeMounts:
        - name: data
          mountPath: /data
  volumes:
    - name: data
      persistentVolumeClaim:
        claimName: pvc-manual
```

Commands to try:

```bash
kubectl apply -f pvc-demo.yaml
kubectl get pvc                                  # STATUS Bound, VOLUME pv-manual-1gi
kubectl get pv                                   # PV now shows CLAIM default/pvc-manual
kubectl delete pod pvc-demo && kubectl apply -f pvc-demo.yaml
kubectl exec pvc-demo -- cat /data/hello.txt     # data survived the Pod being recreated
```

What a `Pending` PVC usually means:

- No PV matches the request (wrong `storageClassName`, access mode not offered, or not enough capacity). Check with `kubectl describe pvc <name>`; the Events section says `no persistent volumes available for this claim`.
- The named StorageClass does not exist, or the cluster has no default StorageClass and the PVC did not specify one.
- The StorageClass uses `volumeBindingMode: WaitForFirstConsumer` and no Pod is using the PVC yet. This is normal; the PVC binds once a Pod is scheduled.
- The provisioner Pod (CSI driver) is not running or lacks cloud permissions.

## 5. StorageClass

A `StorageClass` describes a "type" of storage the cluster can create on demand and names the **provisioner** that does the work. Each class can carry provisioner-specific `parameters` (disk type, IOPS, filesystem, encryption) and its own reclaim policy.

Common provisioners:

| Environment | Provisioner | Default class name |
|---|---|---|
| minikube | `k8s.io/minikube-hostpath` | `standard` |
| kind | `rancher.io/local-path` | `standard` |
| AWS EKS | `ebs.csi.aws.com` (EBS CSI driver) | `gp2` (in-tree, legacy) or `gp3` with the CSI add-on |
| GKE | `pd.csi.storage.gke.io` | `standard-rwo` |
| AKS | `disk.csi.azure.com` | `default` / `managed-csi` |
| Any cluster, RWX | `efs.csi.aws.com`, `nfs.csi.k8s.io`, Longhorn, Rook-Ceph | varies |

`volumeBindingMode`:

- `Immediate` (default) - the PV is provisioned and bound as soon as the PVC is created, without knowing where the Pod will run. Can produce a disk in a different availability zone than the Pod.
- `WaitForFirstConsumer` - provisioning is delayed until a Pod using the PVC is scheduled, so the PV is created in the right zone / on the right node. Recommended for cloud block storage and `local` volumes.

The default class is marked with the annotation `storageclass.kubernetes.io/is-default-class: "true"`. A PVC with no `storageClassName` uses it; a PVC with `storageClassName: ""` explicitly asks for static binding only.

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: gp3-fast
  annotations:
    storageclass.kubernetes.io/is-default-class: "false"
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  iops: "4000"
  throughput: "250"
  encrypted: "true"
  csi.storage.k8s.io/fstype: ext4
reclaimPolicy: Delete
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
```

Commands to try:

```bash
kubectl get sc                                           # (default) marker shows the default class
kubectl describe sc standard                             # on minikube: provisioner k8s.io/minikube-hostpath
kubectl get sc standard -o jsonpath='{.volumeBindingMode}{"\n"}'
kubectl patch sc standard -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
```

## 6. Dynamic provisioning

With static provisioning an admin has to pre-create every PV. Dynamic provisioning removes that step: the PVC names a StorageClass, the class's provisioner creates the real storage and a matching PV object, and the PVC is bound to it automatically.

```
  PVC created                    StorageClass                  Provisioner / CSI driver
  storageClassName: standard --> provisioner:            -->  creates real disk / dir
                                 k8s.io/minikube-hostpath      (e.g. /tmp/hostpath-provisioner/...)
                                                                      |
                                                                      v
  PVC status: Bound    <--  binding  <--   PV object created automatically
  (Pod can now mount it)                   (reclaimPolicy copied from the class)
```

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: pvc-dynamic
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: standard      # minikube default class; omit to use the cluster default
  resources:
    requests:
      storage: 1Gi
```

Commands to try:

```bash
kubectl apply -f pvc-dynamic.yaml
kubectl get pvc pvc-dynamic -w                   # Pending -> Bound within a few seconds on minikube
kubectl get pv                                   # a pvc-<uuid> PV appeared, RECLAIM POLICY Delete
kubectl delete pvc pvc-dynamic && kubectl get pv # the PV is deleted too (policy Delete)
```

## PV / PVC lifecycle

```
 +---------------+     +-------------+     +-------------+     +----------------+
 | Provisioning  | --> |   Binding   | --> |    Using    | --> |   Reclaiming   |
 +---------------+     +-------------+     +-------------+     +----------------+
  static: admin         PVC matched to      Pod mounts the      PVC deleted ->
  creates PV            a PV (class, mode,  PVC; PV protected   Retain : PV Released,
  dynamic: SC +         capacity); 1:1      by finalizer        data kept
  provisioner create    relationship        while in use        Delete : PV + disk
  PV on demand                                                  removed
                                                                Recycle: deprecated
   PV: Available  ------>  PV: Bound  -------------------->  PV: Released / gone
```

## Useful commands summary

```bash
kubectl get pv,pvc,sc                      # one view of all storage objects
kubectl describe pvc <name>                # Events explain Pending / binding failures
kubectl describe pv <name>                 # shows Claim, Reclaim Policy, Source
kubectl get events --field-selector reason=ProvisioningFailed
```

## Key takeaways

1. `emptyDir` is for scratch data and sidecar sharing; it dies with the Pod.
2. `hostPath` ties data to a node and is a security risk; keep it to minikube and node agents.
3. PV = the storage, PVC = the request. Pods always reference the PVC.
4. Access modes are per node (RWO/ROX/RWX) except RWOP, which is per Pod.
5. `Retain` keeps data after the claim is deleted, `Delete` removes it; `Recycle` is deprecated.
6. StorageClass + provisioner gives dynamic provisioning; prefer `WaitForFirstConsumer` on cloud clusters.
7. A `Pending` PVC almost always means no matching PV, no provisioner, or it is waiting for a consumer Pod.

## References

- Kubernetes Volumes: https://kubernetes.io/docs/concepts/storage/volumes/
- Persistent Volumes: https://kubernetes.io/docs/concepts/storage/persistent-volumes/
- Storage Classes: https://kubernetes.io/docs/concepts/storage/storage-classes/
- Dynamic Volume Provisioning: https://kubernetes.io/docs/concepts/storage/dynamic-provisioning/
- Configure a Pod to Use a PersistentVolume: https://kubernetes.io/docs/tasks/configure-pod-container/configure-persistent-volume-storage/
- Pod Security Standards (hostPath restrictions): https://kubernetes.io/docs/concepts/security/pod-security-standards/
- AWS EBS CSI driver: https://github.com/kubernetes-sigs/aws-ebs-csi-driver
- minikube storage: https://minikube.sigs.k8s.io/docs/handbook/persistent_volumes/
