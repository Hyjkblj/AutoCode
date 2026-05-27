package com.autocode.protocol.payload;

import java.util.List;

public class ClarificationRequestedPayload {
    private String question;
    private List<String> options;
    private String context;
    private String stage;

    public String getQuestion() { return question; }
    public void setQuestion(String question) { this.question = question; }
    public List<String> getOptions() { return options; }
    public void setOptions(List<String> options) { this.options = options; }
    public String getContext() { return context; }
    public void setContext(String context) { this.context = context; }
    public String getStage() { return stage; }
    public void setStage(String stage) { this.stage = stage; }
}
