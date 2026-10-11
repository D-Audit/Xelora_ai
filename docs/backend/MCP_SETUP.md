# 🔌 MCP Server Setup & Usage

## ✅ **MCP Server is NOW WORKING!**

Your Excel agent can now be used by Claude Desktop, Cursor IDE, and any MCP-compatible AI tool!

---

## 📊 **What's Available:**

- **MCP Server Name:** `ai-excel-agent`
- **Skills Exposed:** 67 Excel skills
- **Protocol:** MCP 1.29.0 (stdio)
- **Status:** ✅ Ready to use

---

## 🚀 **How to Start the MCP Server:**

### **Option 1: Direct Python**
```bash
python -m mcp_server.server
```

### **Option 2: Using the Startup Script**
```bash
python start_mcp.py
```

The server will wait for MCP client connections via stdio.

---

## 🔗 **Connect Claude Desktop:**

### **Step 1: Find Claude Desktop Config**

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

**Full path example:**
```
C:\Users\HP\AppData\Roaming\Claude\claude_desktop_config.json
```

### **Step 2: Add Your MCP Server**

Edit the config file and add:

```json
{
  "mcpServers": {
    "excel-agent": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "C:\\Users\\HP\\Downloads\\xelora-integrated\\xelora-integrated\\backend"
    }
  }
}
```

**Important:** Replace the `cwd` path with YOUR actual backend path!

### **Step 3: Restart Claude Desktop**

Close and reopen Claude Desktop completely.

---

## 🎯 **Test It Works:**

Open Claude Desktop and try:

```
You: "Use the excel-agent to create a new workbook called test.xlsx"

Claude: [Uses your MCP server]
        [Calls create_new_workbook skill]
        ✅ Done!
```

---

## 📋 **Available Skills (67 total):**

### **Core Operations:**
- create_new_workbook
- open_workbook
- create_sheet
- rename_sheet
- delete_sheet
- copy_sheet

### **Data Operations:**
- write_cell
- write_table
- read_range
- insert_formula
- insert_row
- insert_column
- delete_row
- delete_column

### **Formatting:**
- apply_formatting
- format_range
- conditional_formatting
- data_bar_formatting
- color_scale_formatting
- icon_set_formatting
- auto_fit_columns
- freeze_panes

### **Charts:**
- create_chart
- modify_chart
- delete_chart
- position_chart

### **Advanced:**
- create_pivot_table
- refresh_pivot_table
- create_vba_macro
- run_macro
- data_validation
- add_hyperlink
- insert_picture
- export_to_pdf

And many more! See `skills/library/` for the complete list.
