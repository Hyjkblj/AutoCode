package com.autocode.protocol.payload;

public class CodeIndexBuiltPayload {
    private int fileCount;
    private int symbolCount;
    private String summary;

    public int getFileCount() { return fileCount; }
    public void setFileCount(int fileCount) { this.fileCount = fileCount; }
    public int getSymbolCount() { return symbolCount; }
    public void setSymbolCount(int symbolCount) { this.symbolCount = symbolCount; }
    public String getSummary() { return summary; }
    public void setSummary(String summary) { this.summary = summary; }
}
