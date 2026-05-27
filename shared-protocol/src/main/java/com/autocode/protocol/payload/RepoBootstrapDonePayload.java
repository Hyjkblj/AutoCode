package com.autocode.protocol.payload;

public class RepoBootstrapDonePayload {
    private String repoDir;
    private int fileCount;
    private boolean dependenciesInstalled;

    public String getRepoDir() { return repoDir; }
    public void setRepoDir(String repoDir) { this.repoDir = repoDir; }
    public int getFileCount() { return fileCount; }
    public void setFileCount(int fileCount) { this.fileCount = fileCount; }
    public boolean isDependenciesInstalled() { return dependenciesInstalled; }
    public void setDependenciesInstalled(boolean dependenciesInstalled) { this.dependenciesInstalled = dependenciesInstalled; }
}
