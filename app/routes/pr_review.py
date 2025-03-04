from flask import Blueprint, jsonify, request
from controllers.pr_review import process_pr_async
import logging
import traceback

logger = logging.getLogger(__name__)

pr_review_bp = Blueprint('pr_review', __name__)

@pr_review_bp.route('/pr-review', methods=['POST'])
def bitbucket_webhook():
    """Handle Bitbucket PR webhook events"""
    try:
        # Get webhook payload
        payload = request.json
        logger.info(f"Received webhook payload with keys: {list(payload.keys() if payload else {})}")
        
        if not payload:
            return jsonify({"error": "Empty payload"}), 400
            
        # Check if this is a PR event
        if 'pullrequest' not in payload:
            logger.warning("Payload is not a PR event - missing 'pullrequest' key")
            return jsonify({"message": "Not a pull request event, ignoring"}), 200
            
        pr_data = payload['pullrequest']
        
        # Only process created or updated PRs
        event_key = request.headers.get('X-Event-Key', '')
        logger.info(f"Event key: {event_key}")
        
        if not event_key.startswith(('pullrequest:created', 'pullrequest:updated','pullrequest:approved','pullrequest:unapproved')):
            logger.info(f"Ignoring event with key: {event_key}")
            return jsonify({
                "message": f"Ignoring event: {event_key}",
                "pr_id": pr_data.get('id')
            }), 200
            
        # Extract PR details
        pr_id = pr_data.get('id')
        repo_info = pr_data.get('destination', {}).get('repository', {})
        repo_full_name = repo_info.get('full_name', '')
        
        logger.info(f"PR ID: {pr_id}, Repo: {repo_full_name}")
        logger.info(f"Repository info: {json.dumps(repo_info)}")
        
        if not pr_id or not repo_full_name:
            logger.error("Missing PR ID or repository name in payload")
            return jsonify({"error": "Missing PR ID or repository name"}), 400
            
        logger.info(f"Processing PR #{pr_id} from repository {repo_full_name}")
        
        # Start the PR analysis process
        process_result = process_pr_async(repo_full_name, pr_id)
        
        return jsonify({
            "message": "PR analysis completed",
            "pr_id": pr_id,
            "repository": repo_full_name,
            "status": "success" if process_result else "error"
        }), 200
        
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(f"Error processing webhook: {str(e)}\n{error_traceback}")
        return jsonify({
            "error": f"Internal server error: {str(e)}",
            "traceback": error_traceback
        }), 500

