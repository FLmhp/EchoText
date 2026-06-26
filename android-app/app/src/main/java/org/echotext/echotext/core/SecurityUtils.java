package org.echotext.echotext.core;

import java.security.GeneralSecurityException;
import java.security.SecureRandom;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

public final class SecurityUtils {
    private static final SecureRandom RANDOM = new SecureRandom();

    private SecurityUtils() {}

    public static String generateSharedSecret() {
        byte[] bytes = new byte[32];
        RANDOM.nextBytes(bytes);
        return toHex(bytes);
    }

    public static String signPayload(String sharedSecret, Object payload) throws GeneralSecurityException {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(sharedSecret.getBytes(java.nio.charset.StandardCharsets.UTF_8), "HmacSHA256"));
            byte[] digest = mac.doFinal(JsonUtils.canonicalJsonBytes(payload));
            return "sha256=" + toHex(digest);
        } catch (org.json.JSONException exception) {
            throw new GeneralSecurityException("Failed to canonicalize JSON payload", exception);
        }
    }

    public static boolean verifySignature(String sharedSecret, Object payload, String signature)
            throws GeneralSecurityException {
        String expected = signPayload(sharedSecret, payload);
        return expected.equals(signature);
    }

    private static String toHex(byte[] bytes) {
        StringBuilder builder = new StringBuilder(bytes.length * 2);
        for (byte value : bytes) {
            builder.append(String.format("%02x", value));
        }
        return builder.toString();
    }
}
