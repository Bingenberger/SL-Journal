package de.sljournal.android.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class LoginRequest(val password: String, val otp: String, val device: String)

@Serializable
data class LoginResponse(val token: String, val device: String, val api: Int)

@Serializable
data class Me(
    val api: Int,
    val device: String,
    val today: String,
    @SerialName("school_year") val schoolYear: String,
    val types: Map<String, String>,
    @SerialName("case_statuses") val caseStatuses: Map<String, String> = emptyMap(),
    @SerialName("inbox_count") val inboxCount: Int = 0,
)

@Serializable
data class ProjectRef(val id: Int, val name: String = "")

@Serializable
data class CaseRef(val id: Int, val title: String = "")

/**
 * Auswahlwert wie in den Formularen der Weboberfläche: vorhandene Person,
 * Projekt oder Vorgang (kind + id) oder ein neuer Name als Vorschlag (kind + label).
 */
@Serializable
data class Item(
    val kind: String,
    val id: Int? = null,
    val label: String = "",
    val detail: String? = null,
    @SerialName("school_year") val schoolYear: String? = null,
)

@Serializable
data class ItemPage(val items: List<Item> = emptyList(), val more: Boolean = false)

@Serializable
data class Attachment(val id: Int, val name: String, val mime: String = "", val size: Long = 0)

@Serializable
data class Drawing(val id: Int, val title: String = "")

@Serializable
data class SubTask(val id: Int, val text: String, val done: Int = 0, val due: String? = null)

@Serializable
data class Task(
    val id: Int,
    val text: String,
    val due: String? = null,
    val done: Boolean = false,
    @SerialName("completed_at") val completedAt: String? = null,
    @SerialName("parent_id") val parentId: Int? = null,
    @SerialName("entry_id") val entryId: Int? = null,
    val project: ProjectRef? = null,
    val case: CaseRef? = null,
    val subtasks: List<SubTask> = emptyList(),
)

@Serializable
data class Entry(
    val id: Int,
    val date: String,
    val time: String = "",
    val type: String,
    @SerialName("type_label") val typeLabel: String = "",
    val title: String,
    val excerpt: String = "",
    val sender: String = "",
    val recipients: String = "",
    val participants: String = "",
    val tags: List<String> = emptyList(),
    val projects: List<ProjectRef> = emptyList(),
    val cases: List<CaseRef> = emptyList(),
    @SerialName("attachment_count") val attachmentCount: Int = 0,
    @SerialName("drawing_count") val drawingCount: Int = 0,
    // Nur in der Detailansicht gefüllt:
    val body: String = "",
    val agenda: String = "",
    val decisions: String = "",
    @SerialName("needs_review") val needsReview: Boolean = false,
    @SerialName("participant_items") val participantItems: List<Item> = emptyList(),
    @SerialName("project_items") val projectItems: List<Item> = emptyList(),
    @SerialName("case_items") val caseItems: List<Item> = emptyList(),
    val attachments: List<Attachment> = emptyList(),
    val drawings: List<Drawing> = emptyList(),
    val tasks: List<Task> = emptyList(),
)

@Serializable
data class EntryPage(val items: List<Entry>, val total: Int, val page: Int, val pages: Int)

@Serializable
data class TaskGroup(val key: String, val label: String, val tasks: List<Task>)

@Serializable
data class CaseReminder(val id: Int, val title: String, val status: String, @SerialName("follow_up") val followUp: String? = null)

@Serializable
data class CalendarEvent(
    val title: String,
    val time: String = "",
    val end: String = "",
    val location: String = "",
    val calendar: String = "",
    @SerialName("all_day") val allDay: Boolean = false,
)

@Serializable
data class Day(
    val date: String,
    val previous: String,
    val following: String,
    val entries: List<Entry>,
    @SerialName("task_groups") val taskGroups: List<TaskGroup>,
    @SerialName("undated_count") val undatedCount: Int = 0,
    @SerialName("completed_tasks") val completedTasks: List<Task> = emptyList(),
    @SerialName("case_reminders") val caseReminders: List<CaseReminder> = emptyList(),
    val events: List<CalendarEvent> = emptyList(),
    @SerialName("calendar_status") val calendarStatus: String = "",
)

@Serializable
data class TaskList(val items: List<Task>)

@Serializable
data class NewTask(val text: String, val due: String? = null)

/** Daten zum Anlegen oder Bearbeiten eines Eintrags. */
@Serializable
data class EntryDraft(
    val type: String,
    val date: String,
    val time: String,
    val title: String,
    val body: String,
    val agenda: String = "",
    val decisions: String = "",
    val sender: String = "",
    val recipients: String = "",
    val tags: List<String> = emptyList(),
    @SerialName("participant_items") val participantItems: List<Item> = emptyList(),
    @SerialName("project_items") val projectItems: List<Item> = emptyList(),
    @SerialName("case_items") val caseItems: List<Item> = emptyList(),
    val tasks: List<NewTask> = emptyList(),
)

@Serializable
data class TaskDraft(
    val text: String,
    val due: String?,
    @SerialName("entry_id") val entryId: Int? = null,
)

@Serializable
data class ApiError(val error: String = "")

/** Reihenfolge und Beschriftung der Eintragstypen, falls der Server noch nicht geantwortet hat. */
val DEFAULT_TYPES = linkedMapOf(
    "note" to "Notiz",
    "journal" to "Journal",
    "phone" to "Telefonat",
    "meeting" to "Gespräch",
    "protocol" to "Protokoll",
    "mail_in" to "Mail · Eingang",
    "mail_out" to "Mail · Ausgang",
)
