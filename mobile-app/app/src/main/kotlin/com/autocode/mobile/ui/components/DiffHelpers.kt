package com.autocode.mobile.ui.components

internal fun asDiffMarkdown(patch: String): String {
    val normalized = localizeDiffTextForDisplay(patch)
    if (normalized.isBlank()) return "```diff\n# 暂无差异内容\n```"
    val escaped = normalized.replace("```", "``\\`")
    return buildString {
        append("```diff\n")
        append(escaped)
        if (!escaped.endsWith('\n')) append('\n')
        append("```")
    }
}

internal fun localizeDiffMetaLine(line: String): String {
    val trimmed = line.trim()
    return when {
        line.startsWith("diff --git ") -> {
            val parts = line.removePrefix("diff --git ").trim().split(" ")
            val from = parts.getOrNull(0)?.removePrefix("a/").orEmpty()
            val to = parts.getOrNull(1)?.removePrefix("b/").orEmpty()
            if (from.isNotEmpty() && to.isNotEmpty()) "# 文件差异: $from -> $to"
            else "# 文件差异: ${line.removePrefix("diff --git ").trim()}"
        }
        line.startsWith("index ") -> "# 索引: ${line.removePrefix("index ").trim()}"
        line.startsWith("new file mode ") -> "# 新文件模式: ${line.removePrefix("new file mode ").trim()}"
        line.startsWith("deleted file mode ") -> "# 删除文件模式: ${line.removePrefix("deleted file mode ").trim()}"
        line.startsWith("similarity index ") -> "# 相似度: ${line.removePrefix("similarity index ").trim()}"
        line.startsWith("rename from ") -> "# 重命名来源: ${line.removePrefix("rename from ").trim()}"
        line.startsWith("rename to ") -> "# 重命名目标: ${line.removePrefix("rename to ").trim()}"
        line.startsWith("Binary files ") -> "# 二进制文件存在差异"
        line.startsWith("--- ") -> line.replaceFirst("--- ", "--- 原文件 ")
        line.startsWith("+++ ") -> line.replaceFirst("+++ ", "+++ 新文件 ")
        line.startsWith("@@") -> "# 变更区块: $trimmed"
        else -> line
    }
}

private fun localizeDiffTextForDisplay(rawPatch: String): String {
    if (rawPatch.isBlank()) return ""
    val decodedUnicode = decodeEscapedUnicode(rawPatch)
    val fixedEncoding = tryFixUtf8Mojibake(decodedUnicode)
    return fixedEncoding
        .lineSequence()
        .map(::localizeDiffMetaLine)
        .joinToString("\n")
        .trimEnd()
}

private fun decodeEscapedUnicode(text: String): String {
    val unicodeEscape = Regex("""\\u([0-9a-fA-F]{4})""")
    return unicodeEscape.replace(text) { match ->
        runCatching {
            val codePoint = match.groupValues[1].toInt(16)
            codePoint.toChar().toString()
        }.getOrElse { match.value }
    }
}

private fun tryFixUtf8Mojibake(text: String): String {
    if (!looksLikeUtf8Mojibake(text)) return text
    val candidate =
        runCatching { text.toByteArray(Charsets.ISO_8859_1).toString(Charsets.UTF_8) }
            .getOrElse { return text }
    return if (mojibakeScore(candidate) <= mojibakeScore(text)) candidate else text
}

private fun looksLikeUtf8Mojibake(text: String): Boolean =
    text.contains('Ã') ||
        text.contains('Â') ||
        text.contains("ä¸") ||
        text.contains("å") ||
        text.contains("æ")

private fun mojibakeScore(text: String): Int {
    var score = 0
    text.forEach { ch ->
        if (ch == '�') score += 3
        if (ch == 'Ã' || ch == 'Â') score += 2
        if (ch in ''..'') score += 1
    }
    return score
}
