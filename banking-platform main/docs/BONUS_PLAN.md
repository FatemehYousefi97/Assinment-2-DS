# Expert bonus proposals — approval required before implementation

Neither optional bonus has been implemented. The mandatory core remains unchanged until real integration/fault tests pass.

## Bonus I: Live Re-Sharding (+12%)

1. Add shard C (two replicas and its own DB) and an authoritative metadata database for the Shard Map epoch.
2. Implement an online `COPYING → CATCHING_UP → FENCING → ACTIVATED → CLEANUP` migration state machine persisted in metadata.
3. Capture a PostgreSQL-consistent snapshot on B; stream durable ordered changes (transactional outbox/logical decoding) into C with committed offsets and idempotent replay. Keep migrating accounts writable during the copy/catch-up stages.
4. At cutover, fence writes on the old owner in shard-side SQL using a monotonic epoch, drain/block relevant 2PC in-flight prepared transactions, apply final deltas, then atomically activate new ownership. Reject all stale-routed write requests on B.
5. Inject kill/restarts during snapshot, delta replay, fencing and activation. Assert no missing changes, exactly one owner and no duplicate cross-shard effects.

## Bonus II: Autonomous Self-Healing (+10%)

1. Implement a custom reconciler with desired replicas, health probing and a durable container registry/generation per replica slot.
2. Restrict controller access to a dedicated Docker API proxy or similarly narrow capability; explicitly prevent uncontrolled socket exposure.
3. On failure, reconcile existing container state, create a replacement with stable shard/database environment, wait for health, then register it through an updatable Gateway registry.
4. Persist replacement intents before Docker API actions and recover controller crashes idempotently without duplicate healthy replacements.
5. Validate with overlapping transfers and injected replica/controller crashes. Do not enable Docker automatic restart policies or use Swarm, Kubernetes or prebuilt self-healing tools.

### Start condition

After the mandatory stack passes all seven experiments on Docker, request the student's approval before starting either bonus. Both additions substantially expand the test matrix and operational risk.

