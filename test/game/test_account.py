"""Unit tests for Account class."""

import unittest
from unittest.mock import Mock, patch

from src.game.account import Account


class TestAccount(unittest.TestCase):
    """Test cases for Account class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.account_name = "test_account"

    @patch('src.game.account.sync')
    def test_account_initialization(self, mock_sync):
        """Test Account initialization."""
        # Mock the API response
        mock_account_data = Mock()
        mock_sync.return_value = mock_account_data
        
        account = Account(self.account_name, self.mock_client)
        
        # Verify API was called correctly
        mock_sync.assert_called_once_with(account=self.account_name, client=self.mock_client)
        
        # Verify account attributes
        self.assertEqual(account.name, self.account_name)
        self.assertEqual(account._client, self.mock_client)
        self.assertEqual(account._account, mock_account_data)

    @patch('src.game.account.sync')
    def test_account_repr(self, mock_sync):
        """Test Account string representation."""
        mock_sync.return_value = Mock()
        
        account = Account(self.account_name, self.mock_client)
        expected = f"Account({self.account_name})"
        
        self.assertEqual(repr(account), expected)

    @patch('src.game.account.sync')
    @patch('src.game.account.logging')
    def test_account_logging(self, mock_logging, mock_sync):
        """Test that account data is logged during initialization."""
        mock_account_data = Mock()
        mock_sync.return_value = mock_account_data
        
        Account(self.account_name, self.mock_client)
        
        # Verify debug logging was called
        mock_logging.debug.assert_called_once_with(f"account: {mock_account_data}")

    @patch('src.game.account.sync')
    def test_account_with_different_names(self, mock_sync):
        """Test Account with different account names."""
        mock_sync.return_value = Mock()
        
        # Test with different names
        names = ["player1", "test_user", "admin", "special-chars_123"]
        
        for name in names:
            with self.subTest(name=name):
                account = Account(name, self.mock_client)
                self.assertEqual(account.name, name)

    @patch('src.game.account.sync')
    def test_account_api_failure(self, mock_sync):
        """Test Account behavior when API call fails."""
        # Mock API to raise an exception
        mock_sync.side_effect = Exception("API Error")
        
        # Account initialization should raise the exception
        with self.assertRaises(Exception) as context:
            Account(self.account_name, self.mock_client)
        
        self.assertIn("API Error", str(context.exception))

    @patch('src.game.account.sync')
    def test_account_none_response(self, mock_sync):
        """Test Account with None response from API."""
        mock_sync.return_value = None
        
        account = Account(self.account_name, self.mock_client)
        
        # Should still create account with None data
        self.assertEqual(account.name, self.account_name)
        self.assertEqual(account._client, self.mock_client)
        self.assertIsNone(account._account)

    @patch('src.game.account.sync')
    def test_account_client_storage(self, mock_sync):
        """Test that Account stores the client correctly."""
        mock_sync.return_value = Mock()
        mock_client1 = Mock()
        mock_client2 = Mock()
        
        account1 = Account("account1", mock_client1)
        account2 = Account("account2", mock_client2)
        
        # Each account should store its own client
        self.assertEqual(account1._client, mock_client1)
        self.assertEqual(account2._client, mock_client2)
        self.assertNotEqual(account1._client, account2._client)

    @patch('src.game.account.sync')
    def test_account_class_attributes(self, mock_sync):
        """Test Account class attributes."""
        mock_sync.return_value = Mock()
        
        # Check initial class attributes
        self.assertIsNone(Account._account)
        self.assertIsNone(Account._client)
        self.assertIsNone(Account.name)
        
        # Create instance
        account = Account(self.account_name, self.mock_client)
        
        # Instance should have its own attributes
        self.assertIsNotNone(account._account)
        self.assertIsNotNone(account._client)
        self.assertIsNotNone(account.name)
        
        # Class attributes should remain None
        self.assertIsNone(Account._account)
        self.assertIsNone(Account._client)
        self.assertIsNone(Account.name)


if __name__ == '__main__':
    unittest.main()