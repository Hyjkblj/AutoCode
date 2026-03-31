/**
 * Executes shell commands with timeout and bounded output capture.
 */
package com.autocode.agent.runtime.exec;

import java.io.IOException;
import java.io.InputStream;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

public class CommandRunner {
    private static final int OUTPUT_LIMIT_CHARS = 8000;

    public CommandRunResult run(String command, Duration timeout) throws IOException, InterruptedException {
        return run(command, timeout, null);
    }

    public CommandRunResult run(String command, Duration timeout, String workingDirectory) throws IOException, InterruptedException {
        if (command == null || command.isBlank()) {
            return new CommandRunResult(2, "empty command", false);
        }

        List<String> argv = buildShellArgv(command);
        ProcessBuilder pb = new ProcessBuilder(argv);
        pb.redirectErrorStream(true);
        if (workingDirectory != null && !workingDirectory.isBlank()) {
            pb.directory(new File(workingDirectory));
        }

        Process process = pb.start();

        StringBuilder outputBuffer = new StringBuilder();
        AtomicBoolean truncated = new AtomicBoolean(false);
        Thread readerThread = new Thread(() -> drain(process.getInputStream(), outputBuffer, truncated), "command-output-drain");
        readerThread.setDaemon(true);
        readerThread.start();

        boolean finished = process.waitFor(Math.max(1, timeout.toSeconds()), TimeUnit.SECONDS);
        if (!finished) {
            process.destroyForcibly();
            readerThread.join(1000);
            return new CommandRunResult(124, finalizeOutput(outputBuffer, truncated), true);
        }
        readerThread.join(2000);

        return new CommandRunResult(process.exitValue(), finalizeOutput(outputBuffer, truncated), false);
    }

    private void drain(InputStream input, StringBuilder output, AtomicBoolean truncated) {
        byte[] buf = new byte[1024];
        try {
            int read;
            while ((read = input.read(buf)) != -1) {
                if (output.length() >= OUTPUT_LIMIT_CHARS) {
                    truncated.set(true);
                    continue;
                }
                int toAppend = Math.min(read, OUTPUT_LIMIT_CHARS - output.length());
                output.append(new String(buf, 0, toAppend, StandardCharsets.UTF_8));
                if (toAppend < read) {
                    truncated.set(true);
                }
            }
        } catch (IOException ignored) {
        }
    }

    private String finalizeOutput(StringBuilder output, AtomicBoolean truncated) {
        String text = output.toString().trim();
        if (truncated.get()) {
            if (!text.isEmpty()) {
                return text + "\n...[truncated]...";
            }
            return "...[truncated]...";
        }
        return text;
    }

    private List<String> buildShellArgv(String command) {
        String os = System.getProperty("os.name", "").toLowerCase();
        List<String> argv = new ArrayList<>();
        if (os.contains("win")) {
            argv.add("cmd.exe");
            argv.add("/c");
            argv.add(command);
            return argv;
        }
        argv.add("/bin/sh");
        argv.add("-lc");
        argv.add(command);
        return argv;
    }
}

