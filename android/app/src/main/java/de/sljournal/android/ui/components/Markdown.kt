package de.sljournal.android.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp

/**
 * Schlanke Markdown-Darstellung für Eintragstexte: Überschriften, Listen,
 * Zitate sowie fett, kursiv, durchgestrichen und Code im Fließtext. Tabellen und
 * Codeblöcke erscheinen als einfacher Text – vollständig bleibt die Weboberfläche.
 */
@Composable
fun MarkdownText(text: String, modifier: Modifier = Modifier) {
    val blocks = remember(text) { parseBlocks(text) }
    Column(modifier, verticalArrangement = Arrangement.spacedBy(6.dp)) {
        blocks.forEach { block ->
            when (block) {
                is Block.Heading -> Text(
                    inline(block.text),
                    style = when (block.level) {
                        1 -> MaterialTheme.typography.titleLarge
                        2 -> MaterialTheme.typography.titleMedium
                        else -> MaterialTheme.typography.titleSmall
                    },
                    modifier = Modifier.padding(top = 6.dp),
                )
                is Block.Bullet -> Row(Modifier.padding(start = (block.indent * 12).dp)) {
                    Text(block.marker, Modifier.width(22.dp), color = MaterialTheme.colorScheme.primary)
                    Text(inline(block.text), style = MaterialTheme.typography.bodyLarge)
                }
                is Block.Quote -> Row {
                    Text("▍", color = MaterialTheme.colorScheme.outline)
                    Text(inline(block.text), style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                is Block.Code -> Text(block.text, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.bodyMedium)
                is Block.Paragraph -> Text(inline(block.text), style = MaterialTheme.typography.bodyLarge)
            }
        }
    }
}

private sealed interface Block {
    data class Heading(val level: Int, val text: String) : Block
    data class Bullet(val marker: String, val text: String, val indent: Int) : Block
    data class Quote(val text: String) : Block
    data class Code(val text: String) : Block
    data class Paragraph(val text: String) : Block
}

private val BULLET = Regex("""^(\s*)([-*+]|\d+[.)])\s+(.*)$""")
private val HEADING = Regex("""^(#{1,6})\s+(.*)$""")

private fun parseBlocks(text: String): List<Block> {
    val result = mutableListOf<Block>()
    val paragraph = mutableListOf<String>()
    fun flush() {
        if (paragraph.isNotEmpty()) result += Block.Paragraph(paragraph.joinToString("\n"))
        paragraph.clear()
    }
    val lines = text.replace("\r\n", "\n").split("\n")
    var i = 0
    while (i < lines.size) {
        val line = lines[i]
        when {
            line.trimStart().startsWith("```") -> {
                flush()
                val code = mutableListOf<String>()
                i++
                while (i < lines.size && !lines[i].trimStart().startsWith("```")) code += lines[i++]
                result += Block.Code(code.joinToString("\n"))
            }
            line.isBlank() -> flush()
            HEADING.matches(line) -> {
                flush()
                val m = HEADING.find(line)!!
                result += Block.Heading(m.groupValues[1].length, m.groupValues[2])
            }
            BULLET.matches(line) -> {
                flush()
                val m = BULLET.find(line)!!
                val marker = m.groupValues[2].let { if (it.first().isDigit()) it else "•" }
                result += Block.Bullet(marker, m.groupValues[3], m.groupValues[1].length / 2)
            }
            line.startsWith(">") -> {
                flush()
                result += Block.Quote(line.removePrefix(">").trim())
            }
            else -> paragraph += line
        }
        i++
    }
    flush()
    return result
}

private val INLINE = Regex("""\*\*(.+?)\*\*|__(.+?)__|~~(.+?)~~|`([^`]+)`|\*(?!\s)(.+?)\*|_(?!\s)(.+?)_|\[([^\]]+)]\(([^)]+)\)""")

private fun inline(text: String): AnnotatedString = buildAnnotatedString {
    var last = 0
    for (match in INLINE.findAll(text)) {
        append(text.substring(last, match.range.first))
        val g = match.groupValues
        when {
            g[1].isNotEmpty() || g[2].isNotEmpty() -> withStyle(SpanStyle(fontWeight = FontWeight.SemiBold)) { append(inline(g[1].ifEmpty { g[2] })) }
            g[3].isNotEmpty() -> withStyle(SpanStyle(textDecoration = TextDecoration.LineThrough)) { append(g[3]) }
            g[4].isNotEmpty() -> withStyle(SpanStyle(fontFamily = FontFamily.Monospace, background = Color(0x1A7B888C))) { append(g[4]) }
            g[5].isNotEmpty() || g[6].isNotEmpty() -> withStyle(SpanStyle(fontStyle = FontStyle.Italic)) { append(g[5].ifEmpty { g[6] }) }
            g[7].isNotEmpty() -> withStyle(SpanStyle(textDecoration = TextDecoration.Underline)) { append(g[7]) }
        }
        last = match.range.last + 1
    }
    append(text.substring(last))
}
