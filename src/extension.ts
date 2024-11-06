import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import * as cp from 'child_process';

// Interface for metadata about split files
interface SplitFileMetadata {
    originalFile: string;
    parts: string[];
}

// Class to manage split file metadata
class MetadataManager {
    private static readonly METADATA_FILE = '.code-split-metadata.json';
    private metadata: Map<string, SplitFileMetadata>;
    private workspaceRoot: string;

    constructor(workspaceRoot: string) {
        this.workspaceRoot = workspaceRoot;
        this.metadata = new Map();
        this.loadMetadata();
    }

    private get metadataPath(): string {
        return path.join(this.workspaceRoot, MetadataManager.METADATA_FILE);
    }

    private loadMetadata(): void {
        try {
            if (fs.existsSync(this.metadataPath)) {
                const data = JSON.parse(fs.readFileSync(this.metadataPath, 'utf8'));
                this.metadata = new Map(Object.entries(data));
            }
        } catch (error) {
            console.error('Error loading metadata:', error);
        }
    }

    private saveMetadata(): void {
        try {
            const data = Object.fromEntries(this.metadata);
            fs.writeFileSync(this.metadataPath, JSON.stringify(data, null, 2));
        } catch (error) {
            console.error('Error saving metadata:', error);
        }
    }

    public addSplitFile(originalFile: string, parts: string[]): void {
        this.metadata.set(originalFile, { originalFile, parts });
        this.saveMetadata();
    }

    public getSplitFiles(originalFile: string): string[] | undefined {
        return this.metadata.get(originalFile)?.parts;
    }

    public isPartOfSplitFile(filePath: string): string | undefined {
        for (const [original, meta] of this.metadata.entries()) {
            if (meta.parts.includes(filePath)) {
                return original;
            }
        }
        return undefined;
    }

    public getAllSplitFiles(): Map<string, SplitFileMetadata> {
        return new Map(this.metadata);
    }
}

// Virtual document provider for combined view
class CombinedDocumentProvider implements vscode.TextDocumentContentProvider {
    private _onDidChange = new vscode.EventEmitter<vscode.Uri>();
    private metadata: MetadataManager;
    private fileWatchers: Map<string, vscode.FileSystemWatcher> = new Map();

    constructor(metadata: MetadataManager) {
        this.metadata = metadata;
        this.setupFileWatchers();
    }

    private setupFileWatchers(): void {
        // Clear existing watchers
        this.fileWatchers.forEach(watcher => watcher.dispose());
        this.fileWatchers.clear();

        // Set up watchers for all split files
        const allMetadata = this.metadata.getAllSplitFiles();
        for (const [_, meta] of allMetadata) {
            meta.parts.forEach(partPath => {
                const watcher = vscode.workspace.createFileSystemWatcher(partPath);
                watcher.onDidChange(() => {
                    this._onDidChange.fire(vscode.Uri.parse(`code-split:${vscode.Uri.file(meta.originalFile).toString()}`));
                });
                this.fileWatchers.set(partPath, watcher);
            });
        }
    }

    public get onDidChange(): vscode.Event<vscode.Uri> {
        return this._onDidChange.event;
    }

    public async provideTextDocumentContent(uri: vscode.Uri): Promise<string> {
        const originalPath = uri.fsPath;
        const parts = this.metadata.getSplitFiles(originalPath);
        
        if (!parts) {
            return '';
        }

        const contents = await Promise.all(parts.map(async (part) => {
            try {
                const content = await fs.promises.readFile(part, 'utf8');
                return content;
            } catch (error) {
                console.error(`Error reading part ${part}:`, error);
                return '';
            }
        }));

        return contents.join('\n');
    }

    public dispose(): void {
        this.fileWatchers.forEach(watcher => watcher.dispose());
        this.fileWatchers.clear();
        this._onDidChange.dispose();
    }
}

// Function to generate a unique filename
function generateUniqueFilename(originalPath: string): string {
    const dir = path.dirname(originalPath);
    const ext = path.extname(originalPath);
    const baseName = path.basename(originalPath, ext);
    let counter = 1;
    let newPath = path.join(dir, `${baseName}_${counter.toString().padStart(2, '0')}${ext}`);
    
    while (fs.existsSync(newPath)) {
        counter++;
        newPath = path.join(dir, `${baseName}_${counter.toString().padStart(2, '0')}${ext}`);
    }
    
    return newPath;
}

// Function to run a file based on its extension
async function runFile(filePath: string): Promise<void> {
    if (typeof filePath !== 'string') {
        throw new Error('Invalid file path');
    }

    const ext = path.extname(filePath).toLowerCase();
    let command: string;
    
    switch (ext) {
        case '.py':
            command = 'python';
            break;
        case '.js':
            command = 'node';
            break;
        case '.ts':
            command = 'ts-node';
            break;
        default:
            throw new Error(`Unsupported file type: ${ext}`);
    }

    const terminal = vscode.window.createTerminal('Code Split Runner');
    terminal.show();
    terminal.sendText(`${command} "${filePath}"`);
}

// Extension activation
export function activate(context: vscode.ExtensionContext) {
    console.log('Code Split extension is now active!');

    // Get the workspace folder
    let workspaceRoot: string;
    if (vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders.length > 0) {
        workspaceRoot = vscode.workspace.workspaceFolders[0].uri.fsPath;
        console.log('Workspace root:', workspaceRoot);
    } else {
        // If no workspace is open, use the extension's global storage path
        workspaceRoot = context.globalStorageUri.fsPath;
        // Ensure the directory exists
        if (!fs.existsSync(workspaceRoot)) {
            fs.mkdirSync(workspaceRoot, { recursive: true });
        }
        console.log('Using global storage path:', workspaceRoot);
    }

    const metadataManager = new MetadataManager(workspaceRoot);
    const combinedDocProvider = new CombinedDocumentProvider(metadataManager);

    // Register the combined document provider
    context.subscriptions.push(
        vscode.workspace.registerTextDocumentContentProvider('code-split', combinedDocProvider)
    );

    // Command to split a file
    const splitFileCommand = vscode.commands.registerCommand('code-split.splitFile', async () => {
        console.log('Split File command triggered');
        try {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showErrorMessage('No active editor');
                return;
            }

            const filePath = editor.document.uri.fsPath;
            console.log('File to split:', filePath);

            const content = editor.document.getText();
            const lines = content.split('\n');
            const maxLines = vscode.workspace.getConfiguration('code-split').get('maxLinesPerFile', 500);

            // Calculate number of parts needed
            const numParts = Math.ceil(lines.length / maxLines);
            const parts: string[] = [];

            // Create split files
            const ext = path.extname(filePath);
            const base = path.basename(filePath, ext);
            const dir = path.dirname(filePath);

            for (let i = 0; i < numParts; i++) {
                const start = i * maxLines;
                const end = Math.min((i + 1) * maxLines, lines.length);
                const partContent = lines.slice(start, end).join('\n');
                
                const partPath = path.join(dir, `${base}_p${i + 1}.part`);
                
                console.log(`Creating part ${i + 1}:`, partPath);
                fs.writeFileSync(partPath, partContent);
                parts.push(partPath);
            }

            // Save metadata
            metadataManager.addSplitFile(filePath, parts);
            vscode.window.showInformationMessage(`File split into ${numParts} parts`);

            // Create linking file in the same directory as the parts
            const linkFilePath = path.join(dir, `${base}_plink.ts`);
            const importStatements = parts.map((part, index) => {
                const relativePath = `./${path.basename(part)}`;
                return `// @ts-ignore\nimport part${index + 1} from '${relativePath}';`;
            }).join('\n');
            const linkFileContent = `${importStatements}\n\nexport default [${parts.map((_, index) => `part${index + 1}`).join(', ')}];`;
            fs.writeFileSync(linkFilePath, linkFileContent);
            console.log('Linking file created:', linkFilePath);

            // Open the combined view automatically
            const uri = vscode.Uri.file(filePath);
            await vscode.workspace.openTextDocument(uri);
            await vscode.window.showTextDocument(uri, { preview: false });
        } catch (error: any) {
            console.error('Error in split file command:', error);
            vscode.window.showErrorMessage(`Error splitting file: ${error?.message || 'Unknown error occurred'}`);
        }
    });

    // Command to combine split files
    const combineSplitsCommand = vscode.commands.registerCommand('code-split.combineSplits', async () => {
        console.log('Combine Splits command triggered');
        try {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showErrorMessage('No active editor');
                return;
            }

            const filePath = editor.document.uri.fsPath;
            const originalFile = metadataManager.isPartOfSplitFile(filePath) || filePath;
            const parts = metadataManager.getSplitFiles(originalFile);

            if (!parts) {
                vscode.window.showErrorMessage('No split files found to combine');
                return;
            }

            // Read all parts
            const contents = await Promise.all(parts.map(part => fs.promises.readFile(part, 'utf8')));
            const combinedContent = contents.map(content => content.trim()).join('\n');

            // Generate unique filename for combined file
            const combinedPath = generateUniqueFilename(originalFile);

            // Write combined content
            fs.writeFileSync(combinedPath, combinedContent);
            vscode.window.showInformationMessage(`Files combined into: ${path.basename(combinedPath)}`);

            // Open the combined file
            const doc = await vscode.workspace.openTextDocument(combinedPath);
            await vscode.window.showTextDocument(doc);

            return combinedPath;
        } catch (error: any) {
            console.error('Error in combine splits command:', error);
            vscode.window.showErrorMessage(`Error combining files: ${error?.message || 'Unknown error occurred'}`);
            return undefined;
        }
    });

    // Command to combine splits and run
    const combineSplitsAndRunCommand = vscode.commands.registerCommand('code-split.combineSplitsAndRun', async () => {
        console.log('Combine Splits and Run command triggered');
        try {
            const combinedPath = await vscode.commands.executeCommand<string>('code-split.combineSplits');
            if (combinedPath) {
                await runFile(combinedPath);
            }
        } catch (error: any) {
            console.error('Error in combine splits and run command:', error);
            vscode.window.showErrorMessage(`Error combining and running files: ${error?.message || 'Unknown error occurred'}`);
        }
    });

    // Command to show combined view
    const showCombinedViewCommand = vscode.commands.registerCommand('code-split.combineView', async () => {
        console.log('Show Combined View command triggered');
        try {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showErrorMessage('No active editor');
                return;
            }

            const filePath = editor.document.uri.fsPath;
            const originalFile = metadataManager.isPartOfSplitFile(filePath);
            
            if (!originalFile) {
                vscode.window.showErrorMessage('This file is not part of a split file');
                return;
            }

            const uri = vscode.Uri.file(originalFile);
            const doc = await vscode.workspace.openTextDocument(uri);
            await vscode.window.showTextDocument(doc, { preview: false });
        } catch (error: any) {
            console.error('Error in show combined view command:', error);
            vscode.window.showErrorMessage(`Error showing combined view: ${error?.message || 'Unknown error occurred'}`);
        }
    });

    // Register language providers for split files
    const languages = ['python', 'javascript', 'typescript', 'java', 'cpp', 'csharp'];
    languages.forEach(language => {
        context.subscriptions.push(
            vscode.languages.registerDefinitionProvider({ scheme: 'code-split', language }, {
                provideDefinition(document: vscode.TextDocument, position: vscode.Position) {
                    // Implement definition provider
                    return null;
                }
            }),
            vscode.languages.registerHoverProvider({ scheme: 'code-split', language }, {
                provideHover(document: vscode.TextDocument, position: vscode.Position) {
                    // Implement hover provider
                    return null;
                }
            }),
            vscode.languages.registerCompletionItemProvider({ scheme: 'code-split', language }, {
                provideCompletionItems(document: vscode.TextDocument, position: vscode.Position) {
                    // Implement completion provider
                    return null;
                }
            })
        );
    });

    context.subscriptions.push(splitFileCommand, showCombinedViewCommand, combineSplitsCommand, combineSplitsAndRunCommand);
    console.log('Code Split extension commands registered');
}

export function deactivate() {
    console.log('Code Split extension is now deactivated');
}
