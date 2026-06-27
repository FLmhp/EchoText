package org.echotext.echotext.core;

import java.net.DatagramSocket;
import java.net.Inet4Address;
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

    private static boolean isGoodIpv4(String candidate) {
        return isValidIpv4(candidate) && !candidate.startsWith("127.") && !candidate.startsWith("169.254.");
    }

    private static boolean isValidIpv4(String candidate) {
        try {
            InetAddress address = InetAddress.getByName(candidate);
            return address instanceof Inet4Address;
        } catch (UnknownHostException exception) {
            return false;
        }
    }
}
