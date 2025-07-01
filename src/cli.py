#!/usr/bin/env python3
"""Command-line interface for ArtifactsMMO AI Player"""

import argparse
import logging
from typing import List, Optional

from src.lib.log import JSONFormatter


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        prog='artifactsmmo',
        description='ArtifactsMMO AI Player - An autonomous AI player for ArtifactsMMO',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                   # Run with default settings
  %(prog)s -l DEBUG                          # Run with debug logging
  %(prog)s -c MyNewChar                      # Create a new character
  %(prog)s -d OldChar                        # Delete a character
  %(prog)s -p Char1,Char2,Char3             # Run multiple characters in parallel
  %(prog)s -g "reach_level_10"              # Show plan for achieving a goal
  %(prog)s -e "move->fight->rest"           # Evaluate a user-defined plan
  %(prog)s --clean                           # Clear all generated data files
  %(prog)s --daemon                          # Run as a background daemon
        """
    )
    
    # Logging level
    parser.add_argument(
        '-l', '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Set the logging level (default: INFO)'
    )
    
    # Character management
    char_group = parser.add_mutually_exclusive_group()
    char_group.add_argument(
        '-c', '--create-character',
        type=str,
        metavar='CHARACTER_NAME',
        help='Create a new character with the specified name'
    )
    
    char_group.add_argument(
        '-d', '--delete-character',
        type=str,
        metavar='CHARACTER_NAME',
        help='Delete the character with the specified name'
    )
    
    # Parallel execution
    parser.add_argument(
        '-p', '--parallel',
        type=str,
        metavar='CHARACTER1,CHARACTER2,...',
        help='Run multiple characters in parallel (comma-separated list)'
    )
    
    # Daemon mode
    parser.add_argument(
        '--daemon',
        action='store_true',
        help='Run as a background daemon process'
    )
    
    # Clear data
    parser.add_argument(
        '-n', '--clean',
        action='store_true',
        help='Clear all generated data files (world.yaml, map.yaml, knowledge.yaml)'
    )
    
    # Goal planning
    planning_group = parser.add_mutually_exclusive_group()
    planning_group.add_argument(
        '-g', '--goal-planner',
        type=str,
        metavar='GOAL_STRING',
        help='Show the GOAP plan for achieving the specified goal'
    )
    
    planning_group.add_argument(
        '-e', '--evaluate-plan',
        type=str,
        metavar='PLAN_STRING',
        help='Evaluate a user-defined plan (e.g., "move->fight->rest")'
    )
    
    # Additional options
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 1.0.0'
    )
    
    return parser


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments.
    
    Args:
        args: List of arguments to parse. If None, uses sys.argv.
        
    Returns:
        Parsed arguments namespace
    """
    parser = create_parser()
    return parser.parse_args(args)


def validate_args(args: argparse.Namespace) -> bool:
    """Validate parsed arguments for logical consistency.
    
    Args:
        args: Parsed arguments namespace
        
    Returns:
        True if arguments are valid, False otherwise
    """
    # Check for conflicting options
    if args.daemon and (args.goal_planner or args.evaluate_plan):
        logging.error("Cannot use --daemon with goal planning options")
        return False
    
    if args.clean and (args.create_character or args.delete_character):
        logging.error("Cannot clean data while managing characters")
        return False
    
    # Validate character names
    if args.create_character and not args.create_character.strip():
        logging.error("Character name cannot be empty")
        return False
    
    if args.delete_character and not args.delete_character.strip():
        logging.error("Character name cannot be empty")
        return False
    
    # Validate parallel character list
    if args.parallel:
        characters = [c.strip() for c in args.parallel.split(',') if c.strip()]
        if not characters:
            logging.error("No valid character names provided for parallel execution")
            return False
        if len(characters) != len(set(characters)):
            logging.error("Duplicate character names in parallel list")
            return False
    
    return True


def setup_logging(log_level: str) -> None:
    """Configure logging based on the specified level.
    
    Args:
        log_level: Logging level string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {log_level}')
    
    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove any existing handlers to ensure clean setup
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create a console handler with JSON formatter
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    
    # Set the JSON formatter
    json_formatter = JSONFormatter()
    console_handler.setFormatter(json_formatter)
    
    # Add the handler to the root logger
    root_logger.addHandler(console_handler)


def get_character_list(args: argparse.Namespace) -> Optional[List[str]]:
    """Extract the list of characters to run from arguments.
    
    Args:
        args: Parsed arguments namespace
        
    Returns:
        List of character names to run, or None for default behavior
    """
    if args.parallel:
        return [c.strip() for c in args.parallel.split(',') if c.strip()]
    return None