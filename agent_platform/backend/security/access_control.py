"""
Access Control System
Enforces Role-Based Access Control (RBAC) for tools.
"""
import logging
import fnmatch
from typing import List, Dict, Any, Optional
from ..config import config

logger = logging.getLogger(__name__)

class AccessControl:
    def __init__(self):
        self.enabled = False
        self.default_role = "user"
        self.roles = {}
        self._load_config()

    def reload_config(self):
        """Reload configuration"""
        self._load_config()

    def _load_config(self):
        """Load security config"""
        sec_conf = getattr(config, 'security', {})
        
        # Handle Pydantic model or Dict
        if hasattr(sec_conf, 'enabled'):
            self.enabled = sec_conf.enabled
            self.default_role = sec_conf.default_role
            self.roles = sec_conf.roles
        elif isinstance(sec_conf, dict):
            self.enabled = sec_conf.get('enabled', False)
            self.default_role = sec_conf.get('default_role', 'user')
            self.roles = sec_conf.get('roles', {})
        
        # Ensure roles is a dict
        if not isinstance(self.roles, dict):
             # If Pydantic model for roles, convert to dict if possible
             pass

    def check_permission(self, role: str, tool_name: str) -> bool:
        """
        Check if a role has permission to use a tool.
        Returns check result (True/False).
        """
        if not self.enabled:
            return True

        # Use default role if role not found
        if role not in self.roles:
            logger.warning(f"Role '{role}' not found. Using default '{self.default_role}'.")
            role = self.default_role

        role_config = self.roles.get(role, {})
        
        # If role config is object, try accessing attributes, otherwise dict
        if hasattr(role_config, 'allow'):
             allow_list = role_config.allow
             deny_list = role_config.deny
        else:
             allow_list = role_config.get('allow', [])
             deny_list = role_config.get('deny', [])

        # 1. Check Deny (Explicit deny overrides allow)
        for pattern in deny_list:
            if fnmatch.fnmatch(tool_name, pattern):
                logger.warning(f"Access DENIED: Role '{role}' cannot use '{tool_name}' (Matched deny '{pattern}')")
                return False

        # 2. Check Allow
        for pattern in allow_list:
            if fnmatch.fnmatch(tool_name, pattern):
                return True

        logger.warning(f"Access DENIED: Role '{role}' has no allow rule for '{tool_name}'")
        return False

# Global instance
access_control = AccessControl()
