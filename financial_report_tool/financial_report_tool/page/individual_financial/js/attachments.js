/* =====================================================================
   attachments.js
   Files in the chat: choose, drop or paste (up to 5), chips in the composer, links and previews inside a message.
   Part of the Individual Financial page. All files share one scope; the order they are loaded in is in
   individual_financial.js (see README.md in this folder).
   ===================================================================== */

/* ---------------------------------------------------------------------
   ATTACHMENTS  (files waiting in the composer, files shown in a message)
   Files are chosen with the paperclip, dropped on the panel or pasted. They stay in FR.pendingFiles until the comment is sent
   (up to 5, each within the site's file size limit) and travel in the same request as the text (see submitComment).
--------------------------------------------------------------------- */
const MAX_FILES = 5;

// Adds chosen files to the composer. Too many or too big files are refused with a message; a file already chosen is skipped.
function addPendingFiles(list) {
    const limit = (frappe.boot && frappe.boot.max_file_size) || 0;
    let tooBig = 0, extra = 0;
    [...list].forEach(f => {
        if (!f || !f.size && f.size !== 0) return;
        if (FR.pendingFiles.some(p => p.name === f.name && p.size === f.size && p.lastModified === f.lastModified)) return;
        if (limit && f.size > limit) { tooBig++; return; }
        if (FR.pendingFiles.length >= MAX_FILES) { extra++; return; }
        FR.pendingFiles.push(f);
    });
    if (tooBig) frappe.show_alert({ message: `${tooBig === 1 ? 'A file is' : tooBig + ' files are'} larger than ${fileSize(limit)}`, indicator: 'orange' });
    if (extra) frappe.show_alert({ message: `You can attach up to ${MAX_FILES} files to one comment`, indicator: 'orange' });
    paintPendingFiles();
}

// Empties the composer's file list (after a send, and when another row is opened).
function clearPendingFiles() {
    FR.pendingFiles = [];
    paintPendingFiles();
}

// Draws the chips of the files waiting to be sent, each with a small x to take it out again.
function paintPendingFiles() {
    const box = FR.dom.pending;
    if (!box) return;
    box.classList.toggle('has-files', FR.pendingFiles.length > 0);
    box.innerHTML = FR.pendingFiles.map((f, i) =>
        `<span class="fr-pfile" title="${esc(f.name)}">${ICON.file}<b>${esc(f.name)}</b><small>${esc(fileSize(f.size))}</small>` +
        `<button type="button" data-i="${i}" aria-label="Remove ${esc(f.name)}" title="Remove">&times;</button></span>`).join('');
    FR.dom.attach.disabled = FR.pendingFiles.length >= MAX_FILES;
}

// The files of one message: images show a small preview, everything else is a link chip (name + size). Files are private, so the
// link works for logged-in users who may read the comment (Frappe checks that on download).
function filesNode(files) {
    return (files || []).map(f => {
        const url = esc(f.file_url);
        const isImg = /\.(png|jpe?g|gif|webp)$/i.test(f.file_name || '');
        return (isImg ? `<a href="${url}" target="_blank" rel="noopener"><img class="fr-msg-img" src="${url}" alt="${esc(f.file_name)}" loading="lazy"></a>` : '') +
            `<a class="fr-file" href="${url}" target="_blank" rel="noopener" download="${esc(f.file_name)}" title="Open ${esc(f.file_name)}">${ICON.file}<b>${esc(f.file_name)}</b><small>${esc(fileSize(f.file_size || 0))}</small></a>`;
    }).join('');
}
