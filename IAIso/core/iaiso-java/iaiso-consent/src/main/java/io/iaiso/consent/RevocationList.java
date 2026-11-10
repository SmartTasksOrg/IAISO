package io.iaiso.consent;

import java.util.Collections;
import java.util.HashSet;
import java.util.Set;
import java.util.concurrent.locks.ReentrantReadWriteLock;

/**
 * In-memory revocation list. Production deployments should back this
 * with Redis, a database, or similar.
 */
public final class RevocationList {
    private final Set<String> revoked = new HashSet<>();
    private final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();

    public void revoke(String jti) {
        lock.writeLock().lock();
        try {
            revoked.add(jti);
        } finally {
            lock.writeLock().unlock();
        }
    }

    public boolean isRevoked(String jti) {
        lock.readLock().lock();
        try {
            return revoked.contains(jti);
        } finally {
            lock.readLock().unlock();
        }
    }

    public int size() {
        lock.readLock().lock();
        try {
            return revoked.size();
        } finally {
            lock.readLock().unlock();
        }
    }

    public Set<String> snapshot() {
        lock.readLock().lock();
        try {
            return Collections.unmodifiableSet(new HashSet<>(revoked));
        } finally {
            lock.readLock().unlock();
        }
    }
}
