package org.echotext.echotext.core;

import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.InterfaceAddress;
import java.net.NetworkInterface;
import java.net.DatagramSocket;
import java.net.UnknownHostException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Enumeration;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

public final class LanNetwork {
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
        Map<String, String> broadcastsByHost = interfaceBroadcastsByHost();
        for (String host : hosts) {
            String broadcast = broadcastsByHost.get(host);
            if (broadcast == null) {
                broadcast = derivedBroadcastHost(host);
            }
            if (broadcast != null && !targets.contains(broadcast)) {
                targets.add(broadcast);
            }
            for (String extraTarget : legacyPrivateBroadcastTargets(host)) {
                if (!targets.contains(extraTarget)) {
                    targets.add(extraTarget);
                }
            }
        }
        return targets;
    }

    public static List<String> normalizeHosts(String primaryHost, List<String> extraHosts) {
        List<String> hosts = new ArrayList<>();
        if (isValidIpv4(primaryHost)) {
            hosts.add(primaryHost);
        }
        for (String host : extraHosts) {
            if (isValidIpv4(host) && !hosts.contains(host)) {
                hosts.add(host);
            }
        }
        return hosts;
    }

    public static List<String> subnetScanTargets(List<String> hosts) {
        return subnetScanTargets(hosts, 8_192);
    }

    public static List<String> subnetScanTargets(List<String> hosts, int maxHosts) {
        List<String> targets = new ArrayList<>();
        Set<String> localHosts = new LinkedHashSet<>();
        for (String host : hosts) {
            if (isValidIpv4(host)) {
                localHosts.add(host);
            }
        }
        Set<String> seen = new LinkedHashSet<>(localHosts);
        Map<String, Short> prefixesByHost = interfacePrefixesByHost();
        int remaining = Math.max(maxHosts, 0);
        for (String host : localHosts) {
            for (String candidate : scanTargetsForHost(host, prefixesByHost.get(host), remaining)) {
                if (seen.add(candidate)) {
                    targets.add(candidate);
                    remaining -= 1;
                    if (remaining <= 0) {
                        return targets;
                    }
                }
            }
        }
        return targets;
    }

    private static List<String> ipv4Candidates() {
        Set<String> candidates = new LinkedHashSet<>();
        String socketIp = localIpFromSocket();
        if (socketIp != null) {
            candidates.add(socketIp);
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
                    if (address instanceof Inet4Address && !address.isLoopbackAddress()) {
                        candidates.add(address.getHostAddress());
                    }
                }
            }
        } catch (Exception ignored) {
            // Fall through with best-effort candidates.
        }
        return new ArrayList<>(candidates);
    }

    private static Map<String, String> interfaceBroadcastsByHost() {
        Map<String, String> broadcasts = new HashMap<>();
        try {
            Enumeration<NetworkInterface> interfaces = NetworkInterface.getNetworkInterfaces();
            while (interfaces.hasMoreElements()) {
                NetworkInterface networkInterface = interfaces.nextElement();
                if (!networkInterface.isUp() || networkInterface.isLoopback()) {
                    continue;
                }
                for (InterfaceAddress interfaceAddress : networkInterface.getInterfaceAddresses()) {
                    InetAddress address = interfaceAddress.getAddress();
                    InetAddress broadcast = interfaceAddress.getBroadcast();
                    if (address instanceof Inet4Address && broadcast instanceof Inet4Address) {
                        broadcasts.put(address.getHostAddress(), broadcast.getHostAddress());
                    }
                }
            }
        } catch (Exception ignored) {
            // Fall through with /24 best effort fallback.
        }
        return broadcasts;
    }

    private static Map<String, Short> interfacePrefixesByHost() {
        Map<String, Short> prefixes = new HashMap<>();
        try {
            Enumeration<NetworkInterface> interfaces = NetworkInterface.getNetworkInterfaces();
            while (interfaces.hasMoreElements()) {
                NetworkInterface networkInterface = interfaces.nextElement();
                if (!networkInterface.isUp() || networkInterface.isLoopback()) {
                    continue;
                }
                for (InterfaceAddress interfaceAddress : networkInterface.getInterfaceAddresses()) {
                    InetAddress address = interfaceAddress.getAddress();
                    short prefixLength = interfaceAddress.getNetworkPrefixLength();
                    if (address instanceof Inet4Address && prefixLength > 0 && prefixLength <= 32) {
                        prefixes.put(address.getHostAddress(), prefixLength);
                    }
                }
            }
        } catch (Exception ignored) {
            // Fall through with /24 best effort fallback.
        }
        return prefixes;
    }

    private static String localIpFromSocket() {
        try (DatagramSocket socket = new DatagramSocket()) {
            socket.connect(InetAddress.getByName("8.8.8.8"), 53);
            InetAddress address = socket.getLocalAddress();
            if (address instanceof Inet4Address && !address.isLoopbackAddress()) {
                return address.getHostAddress();
            }
        } catch (Exception ignored) {
            // Fall back to interface scan.
        }
        return null;
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

    private static boolean isValidIpv4(String candidate) {
        try {
            InetAddress address = InetAddress.getByName(candidate);
            return address instanceof Inet4Address;
        } catch (UnknownHostException exception) {
            return false;
        }
    }

    private static String derivedBroadcastHost(String host) {
        if (!isValidIpv4(host)) {
            return null;
        }
        String[] octets = host.split("\\.");
        return octets[0] + "." + octets[1] + "." + octets[2] + ".255";
    }

    private static List<String> legacyPrivateBroadcastTargets(String host) {
        if (!isValidIpv4(host)) {
            return Collections.emptyList();
        }
        String[] octets = host.split("\\.");
        int first = Integer.parseInt(octets[0]);
        int second = Integer.parseInt(octets[1]);
        if (first == 10 || (first == 172 && second >= 16 && second <= 31)) {
            return Collections.singletonList(octets[0] + "." + octets[1] + ".255.255");
        }
        return Collections.emptyList();
    }

    private static List<String> scanTargetsForHost(String host, Short prefixLength, int maxHosts) {
        if (!isValidIpv4(host) || maxHosts <= 0) {
            return Collections.emptyList();
        }
        if (prefixLength == null || prefixLength < 1 || prefixLength >= 24) {
            return same24Targets(host, maxHosts);
        }

        long local = ipv4ToLong(host);
        long networkMask = prefixMask(prefixLength);
        long network = local & networkMask;
        long broadcast = network | (~networkMask & 0xFFFF_FFFFL);
        int startBlock = (int) (network >>> 8);
        int endBlock = (int) (broadcast >>> 8);
        int localBlock = (int) (local >>> 8);

        List<String> targets = new ArrayList<>();
        for (int block : ordered24Blocks(startBlock, endBlock, localBlock)) {
            long blockBase = ((long) block) << 8;
            long start = Math.max(blockBase + 1, network + 1);
            long end = Math.min(blockBase + 254, broadcast - 1);
            for (long value = start; value <= end; value++) {
                if (value == local) {
                    continue;
                }
                targets.add(longToIpv4(value));
                if (targets.size() >= maxHosts) {
                    return targets;
                }
            }
        }
        return targets;
    }

    private static List<String> same24Targets(String host, int maxHosts) {
        String[] octets = host.split("\\.");
        String prefix = octets[0] + "." + octets[1] + "." + octets[2] + ".";
        List<String> targets = new ArrayList<>();
        for (int suffix = 1; suffix < 255 && targets.size() < maxHosts; suffix++) {
            String candidate = prefix + suffix;
            if (!candidate.equals(host)) {
                targets.add(candidate);
            }
        }
        return targets;
    }

    private static List<Integer> ordered24Blocks(int startBlock, int endBlock, int localBlock) {
        List<Integer> blocks = new ArrayList<>();
        if (localBlock >= startBlock && localBlock <= endBlock) {
            blocks.add(localBlock);
        }
        for (int offset = 1; offset <= (endBlock - startBlock); offset++) {
            int upper = localBlock + offset;
            int lower = localBlock - offset;
            if (upper <= endBlock) {
                blocks.add(upper);
            }
            if (lower >= startBlock) {
                blocks.add(lower);
            }
        }
        return blocks;
    }

    private static long prefixMask(int prefixLength) {
        return prefixLength == 0 ? 0L : (0xFFFF_FFFFL << (32 - prefixLength)) & 0xFFFF_FFFFL;
    }

    private static long ipv4ToLong(String host) {
        String[] octets = host.split("\\.");
        long value = 0L;
        for (String octet : octets) {
            value = (value << 8) | Integer.parseInt(octet);
        }
        return value & 0xFFFF_FFFFL;
    }

    private static String longToIpv4(long value) {
        return ((value >>> 24) & 0xFF)
                + "."
                + ((value >>> 16) & 0xFF)
                + "."
                + ((value >>> 8) & 0xFF)
                + "."
                + (value & 0xFF);
    }
}
