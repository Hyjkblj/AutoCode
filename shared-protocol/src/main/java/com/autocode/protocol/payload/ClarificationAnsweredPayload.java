package com.autocode.protocol.payload;

public class ClarificationAnsweredPayload {
    private String answer;
    private String originalQuestion;

    public String getAnswer() { return answer; }
    public void setAnswer(String answer) { this.answer = answer; }
    public String getOriginalQuestion() { return originalQuestion; }
    public void setOriginalQuestion(String originalQuestion) { this.originalQuestion = originalQuestion; }
}
