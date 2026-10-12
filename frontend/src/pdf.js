import { formatNumber, itemLabel } from './format.js'

const BLANK = ''

/**
 * Build and download a printable checklist. `sections` are tables: { title?, head, body, columnStyles? }.
 * jsPDF is loaded on demand, so it isn't part of the main bundle.
 */
export async function downloadChecklist({ title, subtitle, sections, filename }) {
  const [{ jsPDF }, { autoTable }] = await Promise.all([import('jspdf'), import('jspdf-autotable')])
  const doc = new jsPDF({ unit: 'pt', format: 'a4' })
  const margin = 40

  doc.setFontSize(16)
  doc.text(title, margin, margin + 6)
  doc.setFontSize(9)
  doc.setTextColor(100)
  const printed = new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Berlin' })
  doc.text(`${subtitle ? `${subtitle}  -  ` : ''}Printed ${printed.format(new Date())}`, margin, margin + 22)
  doc.text('Counted by: ______________________     Signature: ______________________', margin, margin + 36)
  doc.setTextColor(0)

  let y = margin + 52
  for (const { title: sectionTitle, head, body, columnStyles } of sections) {
    if (sectionTitle) {
      doc.setFontSize(11)
      doc.text(sectionTitle, margin, y + 10)
      y += 16
    }
    autoTable(doc, {
      startY: y,
      margin: { left: margin, right: margin },
      head: [head],
      body,
      theme: 'grid',
      styles: { fontSize: 9, cellPadding: 5, minCellHeight: 20, valign: 'middle' },
      headStyles: { fillColor: [241, 245, 249], textColor: 30, fontStyle: 'bold' },
      columnStyles: { 0: { cellWidth: 'auto' }, ...columnStyles },
    })
    y = doc.lastAutoTable.finalY + 20
  }

  doc.save(filename)
}

/** Freezer-count rows: name with packaging, system stock, then blank Cartons / Bags / Pieces. */
export function countingRows(items) {
  return items.map((item) => [itemLabel(item), `${formatNumber(item.quantity)} ${item.unit}`, BLANK, BLANK, BLANK])
}

export const COUNTING_HEAD = ['Item Name', 'System Quantity', 'Cartons', 'Bags/Subs', 'Pieces']
// Room to write in the blank columns.
export const COUNTING_COLUMNS = { 1: { cellWidth: 80, halign: 'right' }, 2: { cellWidth: 60 }, 3: { cellWidth: 60 }, 4: { cellWidth: 60 } }

/** Waste rows: name with packaging, then blank Waste Amount and Reason. */
export function wasteRows(items, label = itemLabel) {
  return items.map((item) => [label(item), BLANK, BLANK])
}

export const WASTE_HEAD = ['Item Name', 'Waste Amount', 'Reason']
export const WASTE_COLUMNS = { 1: { cellWidth: 80 }, 2: { cellWidth: 170 } }
