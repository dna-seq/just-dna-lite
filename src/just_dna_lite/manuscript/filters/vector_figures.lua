-- Swap a drawn figure's PNG for its vector twin in the PDF build (co-author comment C72 on paper v0.7).
-- `manuscript build` converts each SVG that sits beside a PNG of the same name to PDF under the
-- directory in the `vector-figure-dir` metadata, keeping its path relative to the paper; an image
-- whose `.png` has such a PDF is pointed at it. Screenshots have no SVG and stay raster. The paper
-- keeps citing the `.png`, and the .docx never runs this filter.

local vector_dir = nil -- absolute, to look the PDF up
local vector_href = nil -- relative to the LaTeX file, which is what the .tex names

local function exists(path)
  local handle = io.open(path, "rb")
  if handle == nil then
    return false
  end
  handle:close()
  return true
end

return {
  {
    Meta = function(meta)
      if meta["vector-figure-dir"] ~= nil then
        vector_dir = pandoc.utils.stringify(meta["vector-figure-dir"])
        meta["vector-figure-dir"] = nil
      end
      if meta["vector-figure-href"] ~= nil then
        vector_href = pandoc.utils.stringify(meta["vector-figure-href"])
        meta["vector-figure-href"] = nil
      end
      return meta
    end,
  },
  {
    Image = function(image)
      if vector_dir == nil or not image.src:match("%.png$") then
        return nil
      end
      local relative = image.src:gsub("%.png$", ".pdf")
      if exists(vector_dir .. "/" .. relative) then
        image.src = (vector_href or vector_dir) .. "/" .. relative
        return image
      end
      return nil
    end,
  },
}
