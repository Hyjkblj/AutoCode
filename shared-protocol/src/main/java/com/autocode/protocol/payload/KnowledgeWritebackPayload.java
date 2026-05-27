package com.autocode.protocol.payload;

public class KnowledgeWritebackPayload {
    private String projectKey;
    private int filesSummarized;
    private int errorPatternsStored;

    public String getProjectKey() { return projectKey; }
    public void setProjectKey(String projectKey) { this.projectKey = projectKey; }
    public int getFilesSummarized() { return filesSummarized; }
    public void setFilesSummarized(int filesSummarized) { this.filesSummarized = filesSummarized; }
    public int getErrorPatternsStored() { return errorPatternsStored; }
    public void setErrorPatternsStored(int errorPatternsStored) { this.errorPatternsStored = errorPatternsStored; }
}
