/**
 * Result of executing a command in the node runtime.
 */
package com.autocode.agent.runtime.exec;

public class CommandRunResult {
    private final int exitCode;
    private final String output;
    private final boolean timedOut;

    public CommandRunResult(int exitCode, String output, boolean timedOut) {
        this.exitCode = exitCode;
        this.output = output;
        this.timedOut = timedOut;
    }

    public int getExitCode() {
        return exitCode;
    }

    public String getOutput() {
        return output;
    }

    public boolean isTimedOut() {
        return timedOut;
    }
}

