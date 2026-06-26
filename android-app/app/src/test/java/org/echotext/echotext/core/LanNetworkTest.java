package org.echotext.echotext.core;

import static org.junit.Assert.assertEquals;

import java.util.Arrays;

import org.junit.Test;

public class LanNetworkTest {
    @Test
    public void broadcastTargetsIncludeSubnetBroadcastAfterGlobal() {
        assertEquals(
                Arrays.asList("255.255.255.255", "192.168.3.255"),
                LanNetwork.broadcastTargets("192.168.3.27"));
    }
}
