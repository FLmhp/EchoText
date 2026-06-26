package org.echotext.echotext.core;

import java.security.SecureRandom;

public class PairCodeManager {
    public static final long PAIR_CODE_TTL_MILLIS = 300_000L;
    private static final SecureRandom RANDOM = new SecureRandom();

    private String code = rotateInternal();
    private long expiresAt = System.currentTimeMillis() + PAIR_CODE_TTL_MILLIS;

    public synchronized String getCode() {
        if (isExpired()) {
            rotate();
        }
        return code;
    }

    public synchronized boolean matches(String candidate) {
        return !isExpired() && code.equals(candidate == null ? "" : candidate.trim());
    }

    public synchronized String rotate() {
        code = rotateInternal();
        expiresAt = System.currentTimeMillis() + PAIR_CODE_TTL_MILLIS;
        return code;
    }

    public synchronized boolean isExpired() {
        return System.currentTimeMillis() >= expiresAt;
    }

    private static String rotateInternal() {
        return String.format("%06d", RANDOM.nextInt(1_000_000));
    }
}
