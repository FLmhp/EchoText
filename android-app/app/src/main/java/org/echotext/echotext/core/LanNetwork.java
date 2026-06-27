package org.echotext.echotext.core;

import java.net.DatagramSocket;
import java.net.Inet4Address;
import java.net.Inet6Address;
import java.net.InetAddress;
import java.net.NetworkInterface;
import java.net.UnknownHostException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Enumeration;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

public final class LanNetwork {
    private static final String[] PROBE_TARGETS = {"8.8.8.8", "114.114.114.114"};
    public static final int DEFAULT_ECHOTEXT_PORT = 48735;

    public static final class HostEndpoint {
        public final String host;
        public final int port;

        public HostEndpoint(String host, int port) {
            this.host = host;
            this.port = port;
        }
    }

    private LanNetwork() {}

    public static String localLanIp() {
        String best = bestLanIp(lanIpv4Candidates());
        if (best != null) {
            return best;
        }
        return "127.0.0.1";
    }

    public static List<String> lanIpv4Candidates() {
        List<String> candidates = ipv4Candidates();
        List<String> filtered = new ArrayList<>();
        for (String candidate : candidates) {
            if (lanPriority(candidate) > 0 && !filtered.contains(candidate)) {
                filtered.add(candidate);
            }
        }
        filtered.sort((left, right) -> compareIpv4Priority(right, left));
        return filtered;
    }

    public static List<String> lanIpv6Candidates() {
        List<String> filtered = new ArrayList<>();
        for (String candidate : ipv6Candidates()) {
            if (isGoodIpv6(candidate) && !filtered.contains(candidate)) {
                filtered.add(candidate);
            }
        }
        filtered.sort((left, right) -> compareIpv6Priority(right, left));
        return filtered;
    }

    public static boolean shouldPreferSourceHost(String advertisedHost, String sourceHost) {
        if (!isValidIpv4(sourceHost)) {
            return false;
        }
        if (!isValidIpv4(advertisedHost)) {
            return true;
        }
        return lanPriority(sourceHost) > lanPriority(advertisedHost);
    }

    public static List<String> broadcastTargets(String host) {
        return broadcastTargets(Collections.singletonList(host));
    }

    public static List<String> broadcastTargets(List<String> hosts) {
        List<String> targets = new ArrayList<>();
        targets.add("255.255.255.255");
        for (String prefix : ipv4Prefixes24(hosts)) {
            String target = prefix + "255";
            if (!targets.contains(target)) {
                targets.add(target);
            }
        }
        for (String prefix : ipv4Prefixes16(hosts)) {
            String target = prefix + "255.255";
            if (!targets.contains(target)) {
                targets.add(target);
            }
        }
        return targets;
    }

    public static List<String> normalizeHosts(String primaryHost, List<String> extraHosts) {
        List<String> hosts = new ArrayList<>();
        String normalizedPrimary = normalizeIpLiteral(primaryHost);
        if (normalizedPrimary != null) {
            hosts.add(normalizedPrimary);
        }
        for (String host : extraHosts) {
            String normalizedHost = normalizeIpLiteral(host);
            if (normalizedHost != null && !hosts.contains(normalizedHost)) {
                hosts.add(normalizedHost);
            }
        }
        return hosts;
    }

    public static HostEndpoint parseHostEndpoint(String value) {
        return parseHostEndpoint(value, DEFAULT_ECHOTEXT_PORT);
    }

    public static HostEndpoint parseHostEndpoint(String value, int defaultPort) {
        String raw = value == null ? "" : value.trim();
        if (raw.isEmpty()) {
            throw new IllegalArgumentException("empty endpoint");
        }

        String host;
        int port = defaultPort;
        if (raw.startsWith("[")) {
            int closing = raw.indexOf(']');
            if (closing < 0) {
                throw new IllegalArgumentException("invalid IPv6 endpoint");
            }
            host = raw.substring(1, closing).trim();
            String remainder = raw.substring(closing + 1).trim();
            if (!remainder.isEmpty()) {
                if (!remainder.startsWith(":")) {
                    throw new IllegalArgumentException("invalid endpoint port");
                }
                port = parsePort(remainder.substring(1));
            }
        } else if (raw.chars().filter(ch -> ch == ':').count() > 1) {
            host = raw;
        } else if (raw.contains(":")) {
            int separator = raw.lastIndexOf(':');
            host = raw.substring(0, separator).trim();
            port = parsePort(raw.substring(separator + 1));
        } else {
            host = raw;
        }

        String normalizedHost = normalizeIpLiteral(host);
        if (normalizedHost == null) {
            throw new IllegalArgumentException("invalid IP address");
        }
        if (port < 1 || port > 65535) {
            throw new IllegalArgumentException("invalid endpoint port");
        }
        return new HostEndpoint(normalizedHost, port);
    }

    public static String formatHttpHost(String host) {
        String normalizedHost = normalizeIpLiteral(host);
        if (normalizedHost == null) {
            throw new IllegalArgumentException("invalid IP address");
        }
        if (normalizedHost.contains(":")) {
            return "[" + normalizedHost + "]";
        }
        return normalizedHost;
    }

    public static List<String> subnetScanTargets(List<String> hosts) {
        Set<String> localHosts = new LinkedHashSet<>(normalizeHosts("", hosts));
        List<String> targets = new ArrayList<>();
        for (String prefix : ipv4Prefixes24(localHosts)) {
            for (int suffix = 1; suffix < 255; suffix++) {
                String candidate = prefix + suffix;
                if (!localHosts.contains(candidate) && !targets.contains(candidate)) {
                    targets.add(candidate);
                }
            }
        }
        return targets;
    }

    private static List<String> ipv4Candidates() {
        Set<String> candidates = new LinkedHashSet<>();
        candidates.addAll(probeIps());

        String hostname = safeHostname();
        if (hostname != null) {
            try {
                for (InetAddress address : InetAddress.getAllByName(hostname)) {
                    if (address instanceof Inet4Address) {
                        String hostAddress = address.getHostAddress();
                        if (isGoodIpv4(hostAddress)) {
                            candidates.add(hostAddress);
                        }
                    }
                }
            } catch (UnknownHostException ignored) {
                // Fall through with probes and interface scan.
            }
        }

        try {
            Enumeration<NetworkInterface> interfaces = NetworkInterface.getNetworkInterfaces();
            while (interfaces.hasMoreElements()) {
                NetworkInterface networkInterface = interfaces.nextElement();
                if (!networkInterface.isUp() || networkInterface.isLoopback()) {
                    continue;
                }
                Enumeration<InetAddress> addresses = networkInterface.getInetAddresses();
                while (addresses.hasMoreElements()) {
                    InetAddress address = addresses.nextElement();
                    if (address instanceof Inet4Address) {
                        String hostAddress = address.getHostAddress();
                        if (isGoodIpv4(hostAddress)) {
                            candidates.add(hostAddress);
                        }
                    }
                }
            }
        } catch (Exception ignored) {
            // Best effort only.
        }
        return new ArrayList<>(candidates);
    }

    private static List<String> ipv6Candidates() {
        Set<String> candidates = new LinkedHashSet<>();
        String hostname = safeHostname();
        if (hostname != null) {
            try {
                for (InetAddress address : InetAddress.getAllByName(hostname)) {
                    if (address instanceof Inet6Address) {
                        String hostAddress = normalizeIpv6(address.getHostAddress());
                        if (hostAddress != null && isGoodIpv6(hostAddress)) {
                            candidates.add(hostAddress);
                        }
                    }
                }
            } catch (UnknownHostException ignored) {
                // Fall through with an empty hostname result.
            }
        }

        try {
            Enumeration<NetworkInterface> interfaces = NetworkInterface.getNetworkInterfaces();
            while (interfaces.hasMoreElements()) {
                NetworkInterface networkInterface = interfaces.nextElement();
                if (!networkInterface.isUp() || networkInterface.isLoopback()) {
                    continue;
                }
                Enumeration<InetAddress> addresses = networkInterface.getInetAddresses();
                while (addresses.hasMoreElements()) {
                    InetAddress address = addresses.nextElement();
                    if (address instanceof Inet6Address) {
                        String hostAddress = normalizeIpv6(address.getHostAddress());
                        if (hostAddress != null && isGoodIpv6(hostAddress)) {
                            candidates.add(hostAddress);
                        }
                    }
                }
            }
        } catch (Exception ignored) {
            // Best effort only.
        }

        return new ArrayList<>(candidates);
    }

    private static List<String> probeIps() {
        List<String> ips = new ArrayList<>();
        for (String target : PROBE_TARGETS) {
            try (DatagramSocket socket = new DatagramSocket()) {
                socket.connect(InetAddress.getByName(target), 80);
                InetAddress address = socket.getLocalAddress();
                if (address instanceof Inet4Address && !address.isLoopbackAddress()) {
                    String hostAddress = address.getHostAddress();
                    if (isGoodIpv4(hostAddress) && !ips.contains(hostAddress)) {
                        ips.add(hostAddress);
                    }
                }
            } catch (Exception ignored) {
                // Try the next probe target.
            }
        }
        return ips;
    }

    private static String safeHostname() {
        try {
            return InetAddress.getLocalHost().getHostName();
        } catch (Exception ignored) {
            return null;
        }
    }

    private static List<String> ipv4Prefixes24(Iterable<String> hosts) {
        List<String> prefixes = new ArrayList<>();
        for (String host : hosts) {
            if (!isValidIpv4(host)) {
                continue;
            }
            String[] octets = host.split("\\.");
            String prefix = octets[0] + "." + octets[1] + "." + octets[2] + ".";
            if (!prefixes.contains(prefix)) {
                prefixes.add(prefix);
            }
        }
        return prefixes;
    }

    private static List<String> ipv4Prefixes16(Iterable<String> hosts) {
        List<String> prefixes = new ArrayList<>();
        for (String host : hosts) {
            if (!isValidIpv4(host)) {
                continue;
            }
            String[] octets = host.split("\\.");
            String prefix = octets[0] + "." + octets[1] + ".";
            if (!prefixes.contains(prefix)) {
                prefixes.add(prefix);
            }
        }
        return prefixes;
    }

    private static String bestLanIp(List<String> candidates) {
        String best = null;
        int bestScore = Integer.MIN_VALUE;
        for (String candidate : candidates) {
            int score = lanPriority(candidate);
            if (score > bestScore) {
                best = candidate;
                bestScore = score;
            }
        }
        return bestScore > 0 ? best : null;
    }

    private static int lanPriority(String candidate) {
        if (!isValidIpv4(candidate)) {
            return 0;
        }
        String[] octets = candidate.split("\\.");
        int first = Integer.parseInt(octets[0]);
        int second = Integer.parseInt(octets[1]);
        int fourth = Integer.parseInt(octets[3]);
        if (first == 127 || first == 169 || (first == 0 && second == 0)) {
            return 0;
        }

        int score = 10;
        if (first == 192 && second == 168) {
            score = 100;
        } else if (first == 10) {
            score = 90;
        } else if (first == 172 && second >= 16 && second <= 31) {
            score = 80;
        } else if (first == 198 && (second == 18 || second == 19)) {
            score = -40;
        } else if (first >= 1 && first <= 223) {
            score = 40;
        }

        if (fourth == 1) {
            score -= 45;
        }
        return score;
    }

    private static int compareIpv4Priority(String left, String right) {
        int leftScore = lanPriority(left);
        int rightScore = lanPriority(right);
        if (leftScore != rightScore) {
            return Integer.compare(leftScore, rightScore);
        }
        boolean leftPreferred = left.startsWith("192.168.");
        boolean rightPreferred = right.startsWith("192.168.");
        return Boolean.compare(leftPreferred, rightPreferred);
    }

    private static int compareIpv6Priority(String left, String right) {
        int leftScore = ipv6Priority(left);
        int rightScore = ipv6Priority(right);
        return Integer.compare(leftScore, rightScore);
    }

    private static int ipv6Priority(String candidate) {
        try {
            InetAddress address = InetAddress.getByName(candidate);
            if (!(address instanceof Inet6Address)) {
                return 0;
            }
            if (address.isSiteLocalAddress()) {
                return 2;
            }
            return 1;
        } catch (UnknownHostException exception) {
            return 0;
        }
    }

    private static boolean isGoodIpv4(String candidate) {
        return isValidIpv4(candidate) && !candidate.startsWith("127.") && !candidate.startsWith("169.254.");
    }

    private static boolean isGoodIpv6(String candidate) {
        try {
            InetAddress address = InetAddress.getByName(candidate);
            return address instanceof Inet6Address
                    && !address.isLoopbackAddress()
                    && !address.isLinkLocalAddress()
                    && !address.isMulticastAddress()
                    && !address.isAnyLocalAddress();
        } catch (UnknownHostException exception) {
            return false;
        }
    }

    private static boolean isValidIpv4(String candidate) {
        try {
            InetAddress address = InetAddress.getByName(candidate);
            return address instanceof Inet4Address;
        } catch (UnknownHostException exception) {
            return false;
        }
    }

    private static int parsePort(String rawPort) {
        try {
            return Integer.parseInt(rawPort.trim());
        } catch (NumberFormatException exception) {
            throw new IllegalArgumentException("invalid endpoint port", exception);
        }
    }

    private static String normalizeIpLiteral(String candidate) {
        if (candidate == null) {
            return null;
        }
        String stripped = candidate.trim();
        if (stripped.isEmpty()) {
            return null;
        }
        if (isValidIpv4(stripped)) {
            return stripped;
        }
        return normalizeIpv6(stripped);
    }

    private static String normalizeIpv6(String candidate) {
        String stripped = candidate.trim();
        if (stripped.startsWith("[") && stripped.endsWith("]")) {
            stripped = stripped.substring(1, stripped.length() - 1);
        }
        int scopeIndex = stripped.indexOf('%');
        if (scopeIndex >= 0) {
            stripped = stripped.substring(0, scopeIndex);
        }
        try {
            InetAddress address = InetAddress.getByName(stripped);
            if (address instanceof Inet6Address) {
                return address.getHostAddress();
            }
        } catch (UnknownHostException ignored) {
            return null;
        }
        return null;
    }
}
