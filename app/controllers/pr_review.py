import logging
import os
import requests
import json
import base64
import traceback
from flask import jsonify, request

logger = logging.getLogger(__name__)

# Bitbucket config
BITBUCKET_API_BASE = os.environ.get('BITBUCKET_API_BASE', 'YOUR BITBUCKET_API_BASE')
BITBUCKET_WORKSPACE = os.environ.get('BITBUCKET_WORKSPACE', '')
BITBUCKET_USERNAME = os.environ.get('BITBUCKET_USERNAME', 'YOUR BITBUCKET_USERNAME')
BITBUCKET_APP_PASSWORD = os.environ.get('BITBUCKET_APP_PASSWORD', 'YOUR BITBUCKET_APP_PASSWORD')
BITBUCKET_AUTH = None
if BITBUCKET_USERNAME and BITBUCKET_APP_PASSWORD:
    auth_string = f"{BITBUCKET_USERNAME}:{BITBUCKET_APP_PASSWORD}"
    BITBUCKET_AUTH = base64.b64encode(auth_string.encode()).decode()
    logger.info(f"Bitbucket authentication configured for user: {BITBUCKET_USERNAME}")
else:
    logger.warning("Bitbucket authentication not configured. API calls will be unauthenticated.")

# Configuration
MAX_FILES_TO_REVIEW = 10
MAX_DIFF_SIZE = 50000
IGNORE_FILE_TYPES = ['.md', '.txt', '.json', '.yaml', '.yml', '.lock', '.svg', '.png', '.jpg', '.jpeg', '.gif']
MAX_COMMENT_LENGTH = 50000

def process_pr_async(repo_full_name, pr_id):
    """Start PR processing in a background thread"""
    thread = threading.Thread(target=process_pr, args=(repo_full_name, pr_id))
    thread.daemon = True  # Daemon threads exit when the main program exits
    thread.start()
    logger.info(f"Started background processing for PR #{pr_id}")
    return thread


def process_pr(repo_full_name, pr_id):
   """Process a pull request"""
    try:
        logger.info(f"Starting PR analysis for {repo_full_name} PR #{pr_id}")
        
        if '/' not in repo_full_name:
            error_msg = f"Invalid repository name format: {repo_full_name}. Expected format: workspace/repo_slug"
            logger.error(error_msg)
            return False
            
        workspace, repo_slug = repo_full_name.split('/')
        logger.info(f"Workspace: {workspace}, Repo slug: {repo_slug}")
        
        # Get PR diff
        logger.info(f"Getting diff for PR #{pr_id}")
        diff_content = get_pr_diff(workspace, repo_slug, pr_id)
        if not diff_content:
            logger.error(f"Failed to get diff for PR #{pr_id}")
            add_pr_comment(workspace, repo_slug, pr_id, "⚠️ Error: Could not retrieve the diff for this PR. Please check if the PR exists and is accessible.")
            return False
            
        # Parse diff to extract changed files
        logger.info(f"Parsing diff with length: {len(diff_content)} characters")
        changed_files = parse_diff(diff_content)
        logger.info(f"Found {len(changed_files)} changed files in PR #{pr_id}")
        
        if not changed_files:
            logger.info(f"No relevant files to review in PR #{pr_id}")
            add_pr_comment(workspace, repo_slug, pr_id, 
                          "I didn't find any substantial code changes to review in this PR.")
            return True
            
        # Limit the number of files to analyze
        files_to_analyze = select_files_to_analyze(changed_files)
        logger.info(f"Selected {len(files_to_analyze)} files for analysis")
        
        # Get file contents
        for file_info in files_to_analyze:
            logger.info(f"Getting content for file: {file_info['path']}")
            file_content = get_file_content(workspace, repo_slug, pr_id, file_info['path'])
            if file_content:
                file_info['content'] = file_content
                logger.info(f"Got content for {file_info['path']}, length: {len(file_content)} chars")
            else:
                logger.warning(f"Could not get content for {file_info['path']}")
        
        # Analyze files
        logger.info(f"Starting analysis of {len(files_to_analyze)} files")
        results = analyze_files(files_to_analyze)
        logger.info(f"results======>{results}")
        logger.info(f"Analysis complete, got results for {len(results)} files")
        
        # Post comment with analysis results
        if results:
            logger.info("Formatting analysis results")
            comment = format_analysis_results(results, files_to_analyze)
            logger.info(f"Posting comment with length: {len(comment)} chars")
            comment_result = add_pr_comment(workspace, repo_slug, pr_id, comment)
            if not comment_result:
                logger.error("Failed to post comment to PR")
                return False
            logger.info("Successfully posted PR comment")
        else:
            logger.info("No analysis results to post")
            add_pr_comment(workspace, repo_slug, pr_id, 
                          "I've reviewed the changes but didn't find any significant issues to report.")
        
        return True
            
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(f"Error processing PR #{pr_id}: {str(e)}\n{error_traceback}")
        try:
            add_pr_comment(workspace, repo_slug, pr_id, 
                          f"⚠️ An error occurred while analyzing this PR: {str(e)}")
                          except Exception as comment_error:
            logger.error(f"Failed to add error comment to PR #{pr_id}: {str(comment_error)}")
        return False

def get_pr_diff(workspace, repo_slug, pr_id):
    """Get the diff for a pull request"""
    try:
        url = f"{BITBUCKET_API_BASE}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/diff"
        headers = {}
        if BITBUCKET_AUTH:
            headers['Authorization'] = f"Basic {BITBUCKET_AUTH}"
        
        logger.info(f"Requesting diff from: {url}")
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            logger.info(f"Successfully got diff, length: {len(response.text)} chars")
            return response.text
        else:
            logger.error(f"Failed to get PR diff: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting PR diff: {str(e)}", exc_info=True)
        return None

def parse_diff(diff_content):
    """Parse diff content to extract changed files and their changes"""
    if not diff_content:
        logger.warning("Diff content is empty")
        return []
        
    if len(diff_content) > MAX_DIFF_SIZE:
        logger.warning(f"Diff too large ({len(diff_content)} chars), truncating to {MAX_DIFF_SIZE} chars")
        diff_content = diff_content[:MAX_DIFF_SIZE]
        
    changed_files = []
    current_file = None
    changes = []
    
    try:
        for line in diff_content.split('\n'):
            if line.startswith('diff --git'):
                # Save previous file if exists
                if current_file:
                    changed_files.append({
                        'path': current_file,
                        'changes': '\n'.join(changes),
                        'size': len('\n'.join(changes))
                    })
                    
                # Extract new filename
                parts = line.split(' ')
                if len(parts) >= 4:
                    current_file = parts[3][2:]  # Remove 'b/' prefix
                    changes = []
                elif current_file and (line.startswith('+') or line.startswith('-')):
                # Only collect actual changes (additions/deletions)
                changes.append(line)
        
        # Add the last file
        if current_file and changes:
            changed_files.append({
                'path': current_file,
                'changes': '\n'.join(changes),
                'size': len('\n'.join(changes))
            })
            
        # Filter out ignored file types
        filtered_files = []
        for file_info in changed_files:
            file_ext = os.path.splitext(file_info['path'])[1].lower()
            if file_ext not in IGNORE_FILE_TYPES:
                filtered_files.append(file_info)
                
        logger.info(f"Parsed {len(changed_files)} files from diff, {len(filtered_files)} after filtering")
        return filtered_files
    
    except Exception as e:
        except Exception as e:
        logger.error(f"Error parsing diff: {str(e)}", exc_info=True)
        return []


def select_files_to_analyze(changed_files):
     """Select which files to analyze based on importance and size"""
    try:
        # Sort by size (changes size)
        sorted_files = sorted(changed_files, key=lambda x: x['size'], reverse=True)
        
        # Take the top N files
        selected = sorted_files[:MAX_FILES_TO_REVIEW]
        logger.info(f"Selected {len(selected)} files out of {len(changed_files)} for analysis")
        return selected
    except Exception as e:
        logger.error(f"Error selecting files to analyze: {str(e)}", exc_info=True)
        return []

def get_file_content(workspace, repo_slug, pr_id, file_path):
     """Get the content of a file in the PR"""
    try:
        # Get the latest commit in the PR
        url = f"{BITBUCKET_API_BASE}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}"
        headers = {}
        if BITBUCKET_AUTH:
            headers['Authorization'] = f"Basic {BITBUCKET_AUTH}"
        
        logger.info(f"Getting PR details from: {url}")
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            logger.error(f"Failed to get PR details: {response.status_code} - {response.text}")
            return None
        
        pr_data = response.json()
        source_branch = pr_data.get('source', {}).get('branch', {}).get('name')
        source_commit = pr_data.get('source', {}).get('commit', {}).get('hash')
        
        if not source_branch or not source_commit:
            logger.error("Missing source branch or commit information")
            logger.error(f"PR data keys: {list(pr_data.keys())}")
            logger.error(f"Source data: {json.dumps(pr_data.get('source', {}))}")
            return None
            
        # Get file content
        file_url = f"{BITBUCKET_API_BASE}/repositories/{workspace}/{repo_slug}/src/{source_commit}/{file_path}"
        logger.info(f"Getting file content from: {file_url}")
        file_response = requests.get(file_url, headers=headers)
        
        if file_response.status_code == 200:
            logger.info(f"Got file content, length: {len(file_response.text)} chars")
            return file_response.text
        else:
            logger.error(f"Failed to get file content: {file_response.status_code} - {file_response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting file content for {file_path}: {str(e)}", exc_info=True)
        return None

def analyze_files(files_to_analyze):
    """Analyze files using the AI model"""
    results = []
    
    for i, file_info in enumerate(files_to_analyze):
        try:
            file_path = file_info['path']
            file_ext = os.path.splitext(file_path)[1].lower()
            changes = file_info.get('changes', '')
            content = file_info.get('content', '')
            
            logger.info(f"Analyzing file {i+1}/{len(files_to_analyze)}: {file_path}")
            
            if not content and not changes:
                logger.warning(f"No content or changes for {file_path}, skipping")
                continue
                
            # Prepare prompt for AI analysis
            prompt = f"""
            please help to review this js code
            check any syntax error , add suugested validation error code:{changes} """
            
            # Get AI analysis
            logger.info(f"Generating analysis for {file_path}")
            analysis = generate_analysis(prompt)
            
            if analysis:
                logger.info(f"Analysis generated for {file_path}, length: {len(analysis)} chars")
                results.append({
                    'file_path': file_path,
                    'analysis': analysis
                })
            else:
                logger.warning(f"No analysis generated for {file_path}")
                
        except Exception as e:
            logger.error(f"Error analyzing file {file_info.get('path')}: {str(e)}", exc_info=True)
            
    logger.info(f"Analyzed {len(results)}/{len(files_to_analyze)} files successfully")
    return results

def generate_analysis(prompt):
   """Generate analysis using Ollama API"""
    try:
        logger.info("Calling Ollama API for analysis")
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "options": {
                    "temperature": 0.1,  # Lower temperature for more focused review
                    "top_p": 0.95,
                    "num_predict": 1500  # Limit response size
                }
            }
        )
        
        if response.status_code != 200:
            logger.error(f"Ollama API error: {response.status_code} - {response.text}")
            return None
        
        # Parse response
        generated_text = ""
        logger.info(f"generates text ->: {response.text}")
        logger.info(f"Parsing Ollama response with length: {len(response.text)} chars")
        for line in response.text.strip().split('\n'):
            if line:
                try:
                    data = json.loads(line)
                    if 'response' in data:
                        generated_text += data['response']
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse line as JSON: {line[:50]}...")
                    continue
        
        if not generated_text:
            logger.warning("No text generated from Ollama API")
            
        return generated_text.strip()
        
    except Exception as e:
        logger.error(f"Error generating analysis: {str(e)}", exc_info=True)
        return None

def format_analysis_results(results, files_analyzed):
   """Format analysis results into a PR comment"""
    try:
        if not results:
            logger.warning("No results to format")
            return "I've reviewed this PR but found no significant issues to report."
            
        # Create comment header
        comment = f"# AI Code Review\n\n"
        comment += f"I've analyzed {len(files_analyzed)} files in this PR and found some suggestions:\n\n"
        
        # Add file-specific comments
        for result in results:
            file_path = result['file_path']
            analysis = result['analysis']
            
            comment += f"## {file_path}\n\n"
            comment += f"{analysis}\n\n"
            comment += "---\n\n"
        
        # Add disclaimer
        comment += "Note: This review was generated automatically by an AI assistant. Please consider these suggestions carefully using your own judgment."
        
        # Truncate if too long
       
        logger.info(f"Formatted analysis results, final comment length: {len(comment)} chars")
        return comment
    
    except Exception as e:
        logger.error(f"Error formatting analysis results: {str(e)}", exc_info=True)
        return "Error formatting analysis results. Please check the logs for details."

def add_pr_comment(workspace, repo_slug, pr_id, comment):
     """Add a comment to a PR"""
    try:
        url = f"{BITBUCKET_API_BASE}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/comments"
        headers = {
            'Content-Type': 'application/json'
        }
        
        if BITBUCKET_AUTH:
            headers['Authorization'] = f"Basic {BITBUCKET_AUTH}"
            logger.info("Using Bitbucket authentication")
        else:
            logger.warning("No Bitbucket authentication configured")
            
        data = {
            "content": {
                "raw": comment
            }
        }
        
        logger.info(f"Posting comment to: {url}")
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code in (201, 200):
            logger.info(f"Successfully added comment to PR #{pr_id}")
            return True
        else:
            logger.error(f"Failed to add PR comment: {response.status_code} - {response.text}")
            # Check auth issues
            if response.status_code == 401:
                logger.error("Authentication failed. Check BITBUCKET_USERNAME and BITBUCKET_APP_PASSWORD")
            elif response.status_code == 403:
                logger.error("Permission denied. User may not have write access to this repository")
            elif response.status_code == 404:
                logger.error("Resource not found. Check workspace, repo_slug and PR ID")
            return False
            
    except Exception as e:
        logger.error(f"Error adding PR comment: {str(e)}", exc_info=True)
        return False
