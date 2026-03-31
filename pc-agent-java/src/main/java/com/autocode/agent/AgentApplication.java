/**
 * Node agent entrypoint for the MVP (register, poll tasks, execute, publish events).
 */
package com.autocode.agent;

import com.autocode.agent.config.AgentConfig;
import com.autocode.agent.runtime.AgentRunner;

public class AgentApplication {

    public static void main(String[] args) throws Exception {
        AgentConfig config = AgentConfig.fromEnv();
        AgentRunner runner = new AgentRunner(config);
        runner.start();
    }
}
