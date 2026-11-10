package io.iaiso.consent;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.PrivateKey;
import java.security.PublicKey;
import java.security.Signature;
import java.util.Base64;

/**
 * Minimal JWT codec used by {@link Issuer} and {@link Verifier}.
 * Implements just enough of RFC 7519 to support HS256 and RS256
 * tokens — the spec requirements for IAIso consent.
 */
final class Jwt {
    private static final Base64.Encoder URL_ENCODER = Base64.getUrlEncoder().withoutPadding();
    private static final Base64.Decoder URL_DECODER = Base64.getUrlDecoder();

    private Jwt() {}

    /** Encode bytes as base64url without padding. */
    static String b64url(byte[] data) {
        return URL_ENCODER.encodeToString(data);
    }

    static byte[] b64urlDecode(String s) {
        return URL_DECODER.decode(s);
    }

    /** Sign claims and return a compact JWT string. */
    static String sign(Algorithm alg, JsonObject claims, byte[] hsKey, PrivateKey rsKey) {
        JsonObject header = new JsonObject();
        header.addProperty("alg", alg.wireName());
        header.addProperty("typ", "JWT");
        String headerB64 = b64url(header.toString().getBytes(StandardCharsets.UTF_8));
        String claimsB64 = b64url(claims.toString().getBytes(StandardCharsets.UTF_8));
        String signingInput = headerB64 + "." + claimsB64;
        byte[] sig;
        switch (alg) {
            case HS256:
                sig = hmacSha256(signingInput.getBytes(StandardCharsets.UTF_8), hsKey);
                break;
            case RS256:
                sig = rsaSign(signingInput.getBytes(StandardCharsets.UTF_8), rsKey);
                break;
            default:
                throw new IllegalArgumentException("unsupported algorithm: " + alg);
        }
        return signingInput + "." + b64url(sig);
    }

    /** Parsed JWT with raw header, claims, and signature parts. */
    static final class Parsed {
        final String headerB64;
        final String claimsB64;
        final String signatureB64;
        final JsonObject header;
        final JsonObject claims;
        final byte[] signature;

        Parsed(String h, String c, String s) {
            this.headerB64 = h;
            this.claimsB64 = c;
            this.signatureB64 = s;
            try {
                this.header = JsonParser.parseString(
                    new String(b64urlDecode(h), StandardCharsets.UTF_8)).getAsJsonObject();
                this.claims = JsonParser.parseString(
                    new String(b64urlDecode(c), StandardCharsets.UTF_8)).getAsJsonObject();
                this.signature = b64urlDecode(s);
            } catch (Exception e) {
                throw new ConsentException.InvalidToken("malformed JWT", e);
            }
        }

        String signingInput() {
            return headerB64 + "." + claimsB64;
        }
    }

    /** Parse a compact JWT into header / claims / signature parts. */
    static Parsed parse(String token) {
        if (token == null) {
            throw new ConsentException.InvalidToken("token is null");
        }
        String[] parts = token.split("\\.");
        if (parts.length != 3) {
            throw new ConsentException.InvalidToken("expected 3 JWT parts, got " + parts.length);
        }
        return new Parsed(parts[0], parts[1], parts[2]);
    }

    /** Verify the signature on a parsed JWT. */
    static boolean verifySignature(Parsed parsed, Algorithm alg, byte[] hsKey, PublicKey rsKey) {
        byte[] data = parsed.signingInput().getBytes(StandardCharsets.UTF_8);
        switch (alg) {
            case HS256: {
                byte[] expected = hmacSha256(data, hsKey);
                return constantTimeEquals(expected, parsed.signature);
            }
            case RS256:
                return rsaVerify(data, parsed.signature, rsKey);
            default:
                return false;
        }
    }

    private static byte[] hmacSha256(byte[] data, byte[] key) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(key, "HmacSHA256"));
            return mac.doFinal(data);
        } catch (GeneralSecurityException e) {
            throw new RuntimeException("HMAC failed", e);
        }
    }

    private static byte[] rsaSign(byte[] data, PrivateKey key) {
        try {
            Signature sig = Signature.getInstance("SHA256withRSA");
            sig.initSign(key);
            sig.update(data);
            return sig.sign();
        } catch (GeneralSecurityException e) {
            throw new RuntimeException("RSA sign failed", e);
        }
    }

    private static boolean rsaVerify(byte[] data, byte[] signature, PublicKey key) {
        try {
            Signature sig = Signature.getInstance("SHA256withRSA");
            sig.initVerify(key);
            sig.update(data);
            return sig.verify(signature);
        } catch (GeneralSecurityException e) {
            return false;
        }
    }

    private static boolean constantTimeEquals(byte[] a, byte[] b) {
        if (a == null || b == null || a.length != b.length) {
            return false;
        }
        int diff = 0;
        for (int i = 0; i < a.length; i++) {
            diff |= a[i] ^ b[i];
        }
        return diff == 0;
    }
}
