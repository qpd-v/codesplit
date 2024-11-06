# Code Split

A VSCode extension that helps manage large code files by splitting them into smaller parts while maintaining a unified view.

## Features

- Split large code files into smaller, more manageable parts
- View split files as a single unified document
- Automatic metadata tracking for split files
- Configurable maximum lines per file

## Usage

### Splitting a File

1. Open the file you want to split
2. Press `Ctrl+Shift+P` (Windows/Linux) or `Cmd+Shift+P` (Mac) to open the command palette
3. Type "Split File" and select the "Code Split: Split File" command
4. The file will be split into multiple parts based on the configured maximum lines per file

### Viewing Combined Content

1. Open any part of a split file
2. Press `Ctrl+Shift+P` (Windows/Linux) or `Cmd+Shift+P` (Mac) to open the command palette
3. Type "Show Combined View" and select the "Code Split: Show Combined View" command
4. A new editor will open showing the combined content of all parts

## Configuration

You can configure the maximum number of lines per split file in your VSCode settings:

```json
{
    "code-split.maxLinesPerFile": 200
}
```

## How it Works

When you split a file:
1. The extension creates multiple files with the naming pattern `filename_part1.ext`, `filename_part2.ext`, etc.
2. A metadata file `.code-split-metadata.json` is created/updated to track the relationship between the original file and its parts
3. Each part contains a portion of the original file's content, respecting the configured maximum lines per file

The combined view:
- Creates a virtual document that combines all parts
- Updates automatically when any part is modified
- Maintains the original file's language features and syntax highlighting

## Requirements

- VSCode 1.95.0 or higher
- A workspace folder must be open

## Known Issues

- The extension currently does not handle binary files
- Split files must remain in the same directory as the original file
- Deleting split files manually may cause issues with the combined view

## Release Notes

### 0.0.1

Initial release of Code Split:
- Basic file splitting functionality
- Combined view feature
- Configurable line limit
