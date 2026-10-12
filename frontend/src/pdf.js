import { formatNumber } from './format.js'

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

/**
 * How to multiply up a count, for the floor staff: "1 Carton = 4 Bags | 1 Bag = 12 Pcs".
 * Loose kg / L goods have no piece packaging: their supplier pack ("1 Carton = 15 kg"), or just the unit.
 */
export function packagingInfo(item) {
  const { units_per_carton: perCarton, units_per_subpackage: perBag } = item
  if (perCarton && perBag) {
    const bags = perCarton / perBag
    const carton = Number.isInteger(bags) ? `1 Carton = ${bags} Bags` : `1 Carton = ${perCarton} Pcs`
    return `${carton} | 1 Bag = ${perBag} Pcs`
  }
  if (perCarton) return `1 Carton = ${perCarton} Pcs`
  if (perBag) return `1 Bag = ${perBag} Pcs`
  if (item.pack_size > 1) return `1 Carton = ${formatNumber(item.pack_size)} ${item.unit}`
  return `Count in ${item.unit}`
}

/** Blind-count rows: name and packaging maths, then blank Cartons / Bags / Pieces. No system stock. */
export function countingRows(items) {
  return items.map((item) => [item.name, packagingInfo(item), BLANK, BLANK, BLANK])
}

export const COUNTING_HEAD = ['Item Name', 'Packaging Info', 'Cartons', 'Bags/Subs', 'Pieces']
// Room to write in the blank columns.
export const COUNTING_COLUMNS = { 1: { cellWidth: 150 }, 2: { cellWidth: 55 }, 3: { cellWidth: 55 }, 4: { cellWidth: 55 } }

/** Waste rows: name, packaging maths ('-' for menu items), then blank Waste Amount and Reason. */
export function wasteRows(items, info = packagingInfo) {
  return items.map((item) => [item.name, info(item), BLANK, BLANK])
}

export const WASTE_HEAD = ['Item Name', 'Packaging Info', 'Waste Amount', 'Reason']
export const WASTE_COLUMNS = { 1: { cellWidth: 140 }, 2: { cellWidth: 70 }, 3: { cellWidth: 130 } }
