--[[
docx_tables.lua: readable tables in the manuscript .docx that `manuscript build` writes (build.py).

Pandoc derives a pipe table's column widths from its dash counts, which are all equal, so every
column got the same width and words broke mid-word. For every table this filter:

  * sizes each column from its content, estimated in points for the table font (Arial metrics):
    the longest unbreakable token is the column's minimum, the longest cell text its natural width.
    Natural widths are used when they fit; then body text unwrapped with the header wrapping;
    otherwise each column starts at its minimum and the rest is shared out, short columns first
    (see `fill`). Widths go into the ColSpecs, relative to the text width of the page the table
    lands on;
  * keeps the bold "Table X." (or "Box X.") paragraph directly before a top-level table on the table's page
    ("Table Title" style, keep with next);
  * puts a table whose minimum widths exceed the portrait text width on its own landscape pages,
    together with what introduces it: the caption, a heading with at most one paragraph, or a
    lead-in sentence ending in a colon (top-level tables only);
  * turns a group-heading row (first cell filled, every other cell empty) into one spanning cell;
  * sets cell text in the "Table Text" paragraph style ("Table Heading" in the header row), and
    inline code in the "Table Code" character style;
  * keeps a figure's image on the page of its bold "Figure N." caption ("Figure Image" style, keep
    with next): v0.5 went out with Figure 1 at the foot of one page and its caption on the next.

build.py then pins every table's widths in twips, repeats the borders on each table, keeps rows
from splitting across pages and drops an empty last section (`finish_docx_layout`).

Page geometry and the table font size arrive as metadata set by build.py (docx-*), so the
reference document and this filter share one source; the keys are removed before the writer runs.
]]

local GEOMETRY_KEYS = {
  page_width = 'docx-page-width',      -- portrait page width, twips
  page_height = 'docx-page-height',    -- portrait page height, twips
  margin = 'docx-margin',              -- all four page margins, twips
  font_size = 'docx-table-font-size',  -- table text, points
  cell_margin = 'docx-cell-margin',    -- left and right cell margin each, twips
}
local geometry = {}

local TEXT_STYLE = 'Table Text'
local HEADING_STYLE = 'Table Heading'
local TITLE_STYLE = 'Table Title'
local CODE_STYLE = 'Table Code' -- pandoc's Verbatim Char fixes code at 11 pt, larger than the cell text
local FIGURE_STYLE = 'Figure Image'
local ORIENTATION_ATTR = 'docx-orientation'

-- Arial advance widths in 1/1000 em (Helvetica metrics, which Arial and Liberation Sans share),
-- for code points 32 to 126.
local ASCII_WIDTHS = {
  278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,  -- space to /
  556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,  -- 0 to ?
  1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778, -- @ to O
  667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,  -- P to _
  333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,  -- ` to o
  556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,       -- p to ~
}
local OTHER_WIDTHS = {
  [0x00A0] = 278, [0x00B0] = 400, [0x00B1] = 584, [0x00B2] = 333, [0x00B3] = 333,
  [0x00B5] = 556, [0x00B7] = 278, [0x00D7] = 584, [0x00F7] = 584, [0x0394] = 668,
  [0x03BC] = 556, [0x2013] = 556, [0x2014] = 1000, [0x2018] = 222, [0x2019] = 222,
  [0x201C] = 333, [0x201D] = 333, [0x2022] = 350, [0x2026] = 1000, [0x2192] = 1000,
  [0x2194] = 1000, [0x2212] = 584, [0x2264] = 549, [0x2265] = 549,
}
local DEFAULT_WIDTH = 600   -- other Latin, Greek and symbols
local WIDE_WIDTH = 1000     -- CJK and other full-width scripts
local MONO_WIDTH = 600
local BOLD = 1.1            -- bold Arial runs about a tenth wider
local SCRIPT = 0.65         -- superscript and subscript size
local SAFETY = 1.05         -- kerning-free advance sums still differ a little between renderers
local BORDER_PT = 1.5       -- two half-point borders and rounding

local HYPHEN, EN_DASH, EM_DASH, ZW_SPACE = 0x2D, 0x2013, 0x2014, 0x200B

local function char_width(code, mono)
  if mono then
    return MONO_WIDTH
  end
  if code >= 32 and code <= 126 then
    return ASCII_WIDTHS[code - 31]
  end
  if OTHER_WIDTHS[code] then
    return OTHER_WIDTHS[code]
  end
  if code >= 0x2E80 then
    return WIDE_WIDTH
  end
  return DEFAULT_WIDTH
end

local function is_digit(code)
  return code ~= nil and code >= 0x30 and code <= 0x39
end

-- A measurement walks a cell's inlines and keeps, in 1/1000 em at full size, the widest token
-- (what cannot wrap) and the widest line (the text with no wrapping at all).
local function new_measure()
  return { token = 0, line = 0, max_token = 0, max_line = 0 }
end

local function end_token(m)
  if m.token > m.max_token then
    m.max_token = m.token
  end
  m.token = 0
end

local function end_line(m)
  end_token(m)
  if m.line > m.max_line then
    m.max_line = m.line
  end
  m.line = 0
end

-- Line breaks are allowed at spaces, after an en or em dash, and after a hyphen that is not
-- followed by a digit (UAX #14 keeps "2026-04-11" together, and so does LibreOffice).
local function add_text(m, text, scale, mono)
  local codes = {}
  for _, code in utf8.codes(text) do
    codes[#codes + 1] = code
  end
  for i, code in ipairs(codes) do
    if code == ZW_SPACE then
      end_token(m)
    else
      local width = char_width(code, mono) * scale
      m.token = m.token + width
      m.line = m.line + width
      if code == EN_DASH or code == EM_DASH or (code == HYPHEN and not is_digit(codes[i + 1])) then
        end_token(m)
      end
    end
  end
end

local function add_space(m, scale)
  end_token(m)
  m.line = m.line + char_width(32, false) * scale
end

local measure_inlines

local function measure_inline(m, el, scale, mono)
  local t = el.t
  if t == 'Str' then
    add_text(m, el.text, scale, mono)
  elseif t == 'Space' or t == 'SoftBreak' then
    add_space(m, scale)
  elseif t == 'LineBreak' then
    end_line(m)
  elseif t == 'Code' then
    add_text(m, el.text, scale, true)
  elseif t == 'Math' then
    add_text(m, el.text, scale, mono)
  elseif t == 'Strong' then
    measure_inlines(m, el.content, scale * BOLD, mono)
  elseif t == 'Superscript' or t == 'Subscript' then
    measure_inlines(m, el.content, scale * SCRIPT, mono)
  elseif t == 'Quoted' then
    add_text(m, '\u{201C}', scale, mono)
    measure_inlines(m, el.content, scale, mono)
    add_text(m, '\u{201D}', scale, mono)
  elseif t == 'Note' or t == 'RawInline' or t == 'Image' then
    return
  elseif el.content ~= nil then -- Emph, Underline, Strikeout, SmallCaps, Link, Span, Cite
    measure_inlines(m, el.content, scale, mono)
  end
end

measure_inlines = function(m, inlines, scale, mono)
  for _, el in ipairs(inlines) do
    measure_inline(m, el, scale, mono)
  end
end

local function measure_blocks(blocks, scale)
  local m = new_measure()
  for _, block in ipairs(blocks) do
    if block.t == 'Para' or block.t == 'Plain' then
      measure_inlines(m, block.content, scale, false)
    elseif block.t == 'LineBlock' then
      for _, line in ipairs(block.content) do
        measure_inlines(m, line, scale, false)
        end_line(m)
      end
    else
      add_text(m, pandoc.utils.stringify(block), scale, false)
    end
    end_line(m)
  end
  return m
end

local function to_points(units)
  return units / 1000 * geometry.font_size * SAFETY
end

local function padding_points()
  return 2 * geometry.cell_margin / 20 + BORDER_PT
end

local function text_width_points(landscape)
  local width = landscape and geometry.page_height or geometry.page_width
  return (width - 2 * geometry.margin) / 20
end

local function is_blank(blocks)
  if #blocks == 0 then
    return true
  end
  local has_image = false
  pandoc.Blocks(blocks):walk({ Image = function() has_image = true end })
  return not has_image and pandoc.utils.stringify(blocks):match('^%s*$') ~= nil
end

local function is_group_row(row, ncols)
  local cells = row.cells
  if ncols < 2 or #cells ~= ncols or is_blank(cells[1].contents) then
    return false
  end
  for i = 2, #cells do
    if not is_blank(cells[i].contents) then
      return false
    end
  end
  return true
end

-- Per column, in points with cell padding: the minimum (widest token of any cell), the body's
-- natural width (widest line of a body or foot cell) and the full natural width (header lines
-- too). Cells spanning several columns do not constrain any one of them.
local function column_widths(tbl, ncols)
  local min, body, full = {}, {}, {}
  for i = 1, ncols do
    min[i], body[i], full[i] = 0, 0, 0
  end
  local function visit(rows, scale, header)
    for _, row in ipairs(rows) do
      local col = 1
      for _, cell in ipairs(row.cells) do
        if cell.col_span == 1 and col <= ncols then
          local m = measure_blocks(cell.contents, scale)
          local line = to_points(m.max_line)
          min[col] = math.max(min[col], to_points(m.max_token))
          full[col] = math.max(full[col], line)
          if not header then
            body[col] = math.max(body[col], line)
          end
        end
        col = col + cell.col_span
      end
    end
  end
  visit(tbl.head.rows, BOLD, true)
  for _, section in ipairs(tbl.bodies) do
    visit(section.head, BOLD, true)
    visit(section.body, 1, false)
  end
  visit(tbl.foot.rows, 1, false)
  local pad = padding_points()
  for i = 1, ncols do
    min[i] = min[i] + pad
    body[i] = math.max(body[i] + pad, min[i])
    full[i] = math.max(full[i] + pad, body[i])
  end
  return min, body, full
end

local function sum(values)
  local total = 0
  for _, v in ipairs(values) do
    total = total + v
  end
  return total
end

-- Raise each column from `base` toward `target` with the space left in `available`, smallest need
-- first, each taking at most an equal share of what is left (max-min fair). A short column thus
-- reaches its natural width before a long one is widened, and only the long text wraps; shares in
-- proportion to the need instead squeezed short columns (repository names, dates) into wrapping.
local function fill(base, target, available)
  local widths, order = {}, {}
  for i = 1, #base do
    widths[i], order[i] = base[i], i
  end
  table.sort(order, function(a, b) return target[a] - base[a] < target[b] - base[b] end)
  local spare = available - sum(base)
  for k, i in ipairs(order) do
    local give = math.min(target[i] - base[i], spare / (#order - k + 1))
    widths[i] = base[i] + give
    spare = spare - give
  end
  return widths
end

-- Column widths in points, in order of preference: every line unwrapped (the table may be
-- narrower than the page); body lines unwrapped and the header wrapping into the rest; each
-- column at its minimum, filled toward its body width.
local function distribute(min, body, full, available)
  if sum(full) <= available then
    return full
  elseif sum(body) <= available then
    return fill(body, full, available)
  elseif sum(min) < available then
    return fill(min, body, available)
  end
  local widths = {} -- cannot fit even at the minimums: scale them down, the widest tokens will wrap
  for i = 1, #min do
    widths[i] = min[i] * available / sum(min)
  end
  return widths
end

local function as_paragraphs(blocks)
  return pandoc.Blocks(blocks):walk({
    Plain = function(p) return pandoc.Para(p.content) end,
    Code = function(c) return pandoc.Span({ pandoc.Str(c.text) }, { ['custom-style'] = CODE_STYLE }) end,
  })
end

-- Pandoc's writer styles a Plain in a table cell as "Compact" whatever Div it sits in; a Para
-- takes the Div's custom-style. An empty cell gets an empty Str so its paragraph is styled too,
-- and inline code takes the "Table Code" character style (Verbatim Char at the table size).
local function style_cells(rows, style)
  for _, row in ipairs(rows) do
    for _, cell in ipairs(row.cells) do
      local contents = cell.contents
      if #contents == 0 then
        contents = { pandoc.Para({ pandoc.Str('') }) }
      end
      cell.contents = { pandoc.Div(as_paragraphs(contents), { ['custom-style'] = style }) }
    end
  end
end

local function format_table(tbl)
  local ncols = #tbl.colspecs
  for _, body in ipairs(tbl.bodies) do
    for _, row in ipairs(body.body) do
      if is_group_row(row, ncols) then
        local cell = row.cells[1]
        cell.col_span = ncols
        row.cells = { cell }
      end
    end
  end

  local min, body, full = column_widths(tbl, ncols)
  local landscape = sum(min) > text_width_points(false)
  local available = text_width_points(landscape)
  local widths = distribute(min, body, full, available)
  for i = 1, ncols do
    tbl.colspecs[i] = { tbl.colspecs[i][1], widths[i] / available }
  end
  if landscape then
    tbl.attr.attributes[ORIENTATION_ATTR] = 'landscape'
  end

  style_cells(tbl.head.rows, HEADING_STYLE)
  for _, body in ipairs(tbl.bodies) do
    style_cells(body.head, HEADING_STYLE)
    style_cells(body.body, TEXT_STYLE)
  end
  style_cells(tbl.foot.rows, TEXT_STYLE)
  return tbl
end

-- A paragraph whose pPr holds a sectPr ends the section before it, so the sectPr describes the
-- pages above it. Its mark is set at 1 pt so the break paragraph takes no visible space.
local function section_end(landscape)
  local short, long, m = geometry.page_width, geometry.page_height, geometry.margin
  local size
  if landscape then
    size = string.format('<w:pgSz w:w="%d" w:h="%d" w:orient="landscape"/>', long, short)
  else
    size = string.format('<w:pgSz w:w="%d" w:h="%d"/>', short, long)
  end
  return pandoc.RawBlock('openxml', string.format(
    '<w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/>'
      .. '<w:rPr><w:sz w:val="2"/><w:szCs w:val="2"/></w:rPr>'
      .. '<w:sectPr>%s<w:pgMar w:top="%d" w:right="%d" w:bottom="%d" w:left="%d"'
      .. ' w:header="567" w:footer="567" w:gutter="0"/></w:sectPr></w:pPr></w:p>',
    size, m, m, m, m))
end

local function is_landscape(block)
  return block.t == 'Table' and block.attr.attributes[ORIENTATION_ATTR] == 'landscape'
end

local function starts_with_bold(block, word)
  if block == nil or block.t ~= 'Para' then
    return false
  end
  local first = block.content[1]
  return first ~= nil and first.t == 'Strong' and pandoc.utils.stringify(first):match('^' .. word) ~= nil
end

-- "Box N." captions a table too (Paper 1's Box 1, kept out of the Table numbering).
local function is_caption(block)
  return starts_with_bold(block, 'Table') or starts_with_bold(block, 'Box')
end

-- A paragraph holding one image and nothing else but spaces.
local function is_image_paragraph(block)
  if block.t ~= 'Para' then
    return false
  end
  local images = 0
  for _, inline in ipairs(block.content) do
    if inline.t == 'Image' then
      images = images + 1
    elseif inline.t ~= 'Space' and inline.t ~= 'SoftBreak' then
      return false
    end
  end
  return images == 1
end

-- An image directly above its "Figure N." caption takes the keep-with-next style, so the two never
-- part at a page break. Top level only, like the table captions.
local function keep_figures_with_captions(doc)
  local blocks = doc.blocks
  for i, block in ipairs(blocks) do
    if is_image_paragraph(block) and starts_with_bold(blocks[i + 1], 'Figure') then
      blocks[i] = pandoc.Div({ block }, { ['custom-style'] = FIGURE_STYLE })
    end
  end
  return doc
end

-- How many blocks directly before blocks[t] introduce the table, and so move with it onto a
-- landscape page instead of being stranded on a portrait one: a heading, a heading and one
-- paragraph, a "Table X." caption, or a lead-in sentence ending in a colon.
local function lead_in_count(blocks, t)
  local before, earlier = blocks[t - 1], blocks[t - 2]
  if before == nil then
    return 0
  elseif before.t == 'Header' then
    return 1
  elseif before.t ~= 'Para' then
    return 0
  elseif earlier ~= nil and earlier.t == 'Header' then
    return 2
  elseif is_caption(before) or pandoc.utils.stringify(before):match(':%s*$') then
    return 1
  end
  return 0
end

-- Keep each top-level table's "Table X." caption with it, and put each landscape table, with its
-- introduction, in a landscape section of its own. Landscape tables with nothing else between
-- them share one section instead of leaving an empty page.
local function arrange_tables(doc)
  local blocks = doc.blocks
  local out = pandoc.Blocks({})
  local open_landscape_end = nil -- index in `out` of the section end after the last landscape table
  for i, block in ipairs(blocks) do
    if block.t ~= 'Table' then
      out:insert(block)
    else
      if is_caption(blocks[i - 1]) then -- emitted unchanged just before, so it is out's last block
        out[#out] = pandoc.Div({ blocks[i - 1] }, { ['custom-style'] = TITLE_STYLE })
      end
      if not is_landscape(block) then
        out:insert(block)
      else
        block.attr.attributes[ORIENTATION_ATTR] = nil
        local lead = pandoc.Blocks({})
        for _ = 1, lead_in_count(blocks, i) do
          lead:insert(1, out:remove())
        end
        if open_landscape_end ~= nil and open_landscape_end == #out then
          out:remove()
        elseif #out > 0 then
          out:insert(section_end(false))
        end
        out:extend(lead)
        out:insert(block)
        out:insert(section_end(true))
        open_landscape_end = #out
      end
    end
  end
  doc.blocks = out
  return doc
end

-- Nested tables cannot change page orientation: drop the mark so it never reaches the docx.
local function clear_orientation(doc)
  return doc:walk({
    Table = function(tbl)
      tbl.attr.attributes[ORIENTATION_ATTR] = nil
      return tbl
    end,
  })
end

local function read_geometry(meta)
  for field, key in pairs(GEOMETRY_KEYS) do
    local value = meta[key] and tonumber(pandoc.utils.stringify(meta[key]))
    if value == nil then
      error('docx_tables.lua: metadata ' .. key .. ' is missing; run it through `manuscript build`')
    end
    geometry[field] = value
    meta[key] = nil
  end
  return meta
end

return {
  { Meta = read_geometry },
  { Table = format_table },
  { Pandoc = arrange_tables },
  { Pandoc = clear_orientation },
  { Pandoc = keep_figures_with_captions },
}
