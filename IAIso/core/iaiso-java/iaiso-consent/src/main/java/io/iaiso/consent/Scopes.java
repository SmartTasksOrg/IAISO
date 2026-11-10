package io.iaiso.consent;

import java.util.List;

/**
 * Scope grammar and matching, per {@code spec/consent/README.md §4–§5}.
 * <pre>
 * scope   ::= segment ("." segment)*
 * segment ::= [a-z0-9_-]+
 * </pre>
 *
 * A token granting {@code G} satisfies a request for {@code R} iff:
 * <ul>
 *   <li>{@code G == R} (exact match), or
 *   <li>{@code R} starts with {@code G + "."} (prefix at segment boundary).
 * </ul>
 */
public final class Scopes {
    private Scopes() {}

    public static boolean granted(List<String> granted, String requested) {
        if (requested == null || requested.isEmpty()) {
            throw new IllegalArgumentException("requested scope must be non-empty");
        }
        for (String g : granted) {
            if (g.equals(requested)) {
                return true;
            }
            if (requested.startsWith(g + ".")) {
                return true;
            }
        }
        return false;
    }
}
