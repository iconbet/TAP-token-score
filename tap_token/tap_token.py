from iconservice import *

TAG = 'TapToken'


# An interface of ICON Token Standard, IRC-2
class TokenStandard(ABC):
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def symbol(self) -> str:
        pass

    @abstractmethod
    def decimals(self) -> int:
        pass

    @abstractmethod
    def totalSupply(self) -> int:
        pass

    @abstractmethod
    def balanceOf(self, _owner: Address) -> int:
        pass

    @abstractmethod
    def transfer(self, _to: Address, _value: int, _data: bytes = None):
        pass


# An interface of tokenFallback.
# Receiving SCORE that has implemented this interface can handle
# the receiving or further routine.
class TokenFallbackInterface(InterfaceScore):
    @interface
    def tokenFallback(self, _from: Address, _value: int, _data: bytes):
        pass


class TapToken(IconScoreBase, TokenStandard):
    _BALANCES = 'balances'
    _TOTAL_SUPPLY = 'total_supply'
    _DECIMALS = 'decimals'
    _ADDRESSES = 'addresses'

    _EVEN_DAY_CHANGES = 'even_day_changes'
    _ODD_DAY_CHANGES = 'odd_day_changes'

    _MAX_LOOPS = "max_loops"
    _INDEX_ADDRESS_CHANGES = "index_address_changes"
    _INDEX_UPDATE_BALANCE = "index_update_balance"
    _BALANCE_UPDATE_DB = "balance_update_db"
    _ADDRESS_UPDATE_DB = "address_update_db"

    _DIVIDENDS_SCORE = "dividends_score"
    _BLACKLIST_ADDRESS = "blacklist_address"

    @eventlog(indexed=3)
    def Transfer(self, _from: Address, _to: Address, _value: int, _data: bytes):
        pass

    @eventlog(indexed=1)
    def BlacklistAddress(self, address: Address, note: str):
        pass

    def __init__(self, db: IconScoreDatabase) -> None:
        super().__init__(db)
        self._total_supply = VarDB(self._TOTAL_SUPPLY, db, value_type=int)
        self._decimals = VarDB(self._DECIMALS, db, value_type=int)
        self._addresses = ArrayDB(self._ADDRESSES, db, value_type=Address)
        self._balances = DictDB(self._BALANCES, db, value_type=int)

        self._even_day_changes = ArrayDB(self._EVEN_DAY_CHANGES, db, value_type=Address)
        self._odd_day_changes = ArrayDB(self._ODD_DAY_CHANGES, db, value_type=Address)

        self._changes = [self._even_day_changes, self._odd_day_changes]

        self._max_loop = VarDB(self._MAX_LOOPS, db, value_type=int)
        self._index_update_balance = VarDB(self._INDEX_UPDATE_BALANCE, db, value_type=int)
        self._index_address_changes = VarDB(self._INDEX_ADDRESS_CHANGES, db, value_type=int)

        self._balance_update_db = VarDB(self._BALANCE_UPDATE_DB, db, value_type=int)
        self._address_update_db = VarDB(self._ADDRESS_UPDATE_DB, db, value_type=int)

        self._dividends_score = VarDB(self._DIVIDENDS_SCORE, db, value_type=Address)
        self._blacklist_address = ArrayDB(self._BLACKLIST_ADDRESS, db, value_type=Address)

    def on_install(self, _initialSupply: int, _decimals: int) -> None:
        super().on_install()

        if _initialSupply < 0:
            revert("Initial supply cannot be less than zero")

        if _decimals < 0:
            revert("Decimals cannot be less than zero")

        total_supply = _initialSupply * 10 ** _decimals
        Logger.debug(f'on_install: total_supply={total_supply}', TAG)

        self._total_supply.set(total_supply)
        self._decimals.set(_decimals)
        self._balances[self.owner] = total_supply
        self._addresses.put(self.owner)

    def on_update(self) -> None:
        super().on_update()
        self._max_loop.set(100)
        self._balance_update_db.set(0)
        self._address_update_db.set(0)

    @external
    def untether(self) -> None:
        """
        A function to redefine the value of self.owner once it is possible.
        To be included through an update if it is added to IconService.

        Sets the value of self.owner to the score holding the game treasury.
        """
        if self.tx.origin != self.owner:
            revert(f'Only the owner can call the untether method.')
        pass

    @external
    def get_balances(self, start: int = 0, end: int = -1) -> dict:
        list_len = len(self._addresses)
        if start >= list_len:
            return {}
        if start < 0:
            start = 0
        if end == -1 or end > list_len:
            end = list_len
        balances = {str(self._addresses[i]): self._balances[self._addresses[i]] for i in range(start, end)}
        return balances

    @external(readonly=True)
    def name(self) -> str:
        return "TapToken"

    @external(readonly=True)
    def symbol(self) -> str:
        return "TAP"

    @external(readonly=True)
    def decimals(self) -> int:
        return self._decimals.get()

    @external(readonly=True)
    def totalSupply(self) -> int:
        return self._total_supply.get()

    @external(readonly=True)
    def balanceOf(self, _owner: Address) -> int:
        return self._balances[_owner]

    @external
    def transfer(self, _to: Address, _value: int, _data: bytes = None):
        if _data is None:
            _data = b'None'
        self._transfer(self.msg.sender, _to, _value, _data)

    def _transfer(self, _from: Address, _to: Address, _value: int, _data: bytes):

        # Checks the sending value and balance.
        if _value < 0:
            revert("Transferring value cannot be less than zero")
        if self._balances[_from] < _value:
            revert("Out of balance")

        self._balances[_from] = self._balances[_from] - _value
        self._balances[_to] = self._balances[_to] + _value
        if _to not in self._addresses:
            self._addresses.put(_to)

        if _to.is_contract:
            # If the recipient is SCORE,
            #   then calls `tokenFallback` to hand over control.
            recipient_score = self.create_interface_score(_to, TokenFallbackInterface)
            recipient_score.tokenFallback(_from, _value, _data)

        # Emits an event log `Transfer`
        self.Transfer(_from, _to, _value, _data)
        address_changes = self._changes[self._address_update_db.get()]
        if _from not in self._blacklist_address:
            address_changes.put(_from)
        if _to not in self._blacklist_address:
            address_changes.put(_to)
        Logger.debug(f'Transfer({_from}, {_to}, {_value}, {_data})', TAG)

    def _owner_only(self):
        if self.msg.sender != self.owner:
            revert("Only owner can call this method")

    @external
    def set_max_loop(self, _loops: int = 100) -> None:
        """
        Set the maximum number a for loop can run for any operation
        :param _loops: Maximum number of for loops allowed
        :return:
        """
        self._owner_only()
        self._max_loop.set(_loops)

    @external(readonly=True)
    def get_max_loop(self) -> int:
        """
        Returns the maximum number of for loops allowed in the score
        :return:
        """
        return self._max_loop.get()

    @external
    def set_dividends_score(self, _score: Address) -> None:
        """
        Sets the dividends score address. The function can only be invoked by score owner.
        :param _score: Score address of the dividends contract
        :type _score: :class:`iconservice.base.address.Address`
        """
        self._owner_only()
        self._dividends_score.set(_score)

    @external(readonly=True)
    def get_dividends_score(self) -> Address:
        """
         Returns the roulette score address.
        :return: Address of the roulette score
        :rtype: :class:`iconservice.base.address.Address`
        """
        return self._dividends_score.get()

    @external
    def get_balance_updates(self) -> dict:
        """
        Returns the updated addresses and their balances for today. Returns empty dictionary if the updates has
        completed
        :return: Dictionary contains the addresses and their updated balances. Maximum number of addresses
        and balances returned is defined by the max_loop
        """
        if self.msg.sender != self._dividends_score.get():
            revert("This method can only be called by the dividends distribution contract")
        balance_changes = self._changes[self._balance_update_db.get()]
        length_list = len(balance_changes)

        start = self._index_update_balance.get()
        if start == length_list:
            if self._balance_update_db.get() != self._address_update_db.get():
                self._balance_update_db.set(self._address_update_db.get())
                self._index_update_balance.set(self._index_address_changes.get())
            return {}
        end = min(start + self._max_loop.get(), length_list)
        balances = {str(balance_changes[i]): self._balances[balance_changes[i]] for i in range(start, end)}
        self._index_update_balance.set(end)
        return balances

    @external
    def clear_yesterdays_changes(self) -> bool:
        """
        Clears the array db storing yesterday's changes
        :return: True if the array has been emptied
        """
        if self.msg.sender != self._dividends_score.get():
            revert("This method can only be called by the dividends distribution contract")
        yesterday = (self._address_update_db.get() + 1) % 2
        yesterdays_changes = self._changes[yesterday]
        length_list = len(yesterdays_changes)
        if length_list == 0:
            return True

        loop_count = min(length_list, self._max_loop.get())
        for _ in range(loop_count):
            yesterdays_changes.pop()
        if len(yesterdays_changes) > 0:
            return False
        else:
            return True

    @external(readonly=True)
    def get_blacklist_addresses(self) -> list:
        """
        Returns all the blacklisted addresses(rewards score address and devs team address)
        :return: List of blacklisted address
        :rtype: list
        """
        address_list = []
        for address in self._blacklist_address:
            address_list.append(address)
        return address_list

    @external
    def remove_from_blacklist(self, _address: Address) -> None:
        """
        Removes the address from blacklist.
        Only owner can remove the blacklist address
        :param _address: Address to be removed from blacklist
        :type _address: :class:`iconservice.base.address.Address`
        :return:
        """
        if self.msg.sender == self.owner:
            if _address not in self._blacklist_address:
                revert(f'{_address} not in blacklist address')
            self.BlacklistAddress(_address, "Removed from blacklist")
            top = self._blacklist_address.pop()
            if top != _address:
                for i in range(len(self._blacklist_address)):
                    if self._blacklist_address[i] == _address:
                        self._blacklist_address[i] = top

    @external
    def set_blacklist_address(self, _address: Address) -> None:
        """
        The provided address is set as blacklist address and will be excluded from TAP dividends.
        Only the owner can set the blacklist address
        :param _address: Address to be included in the blacklist
        :type _address: :class:`iconservice.base.address.Address`
        :return:
        """
        if self.msg.sender == self.owner:
            self.BlacklistAddress(_address, "Added to Blacklist")
            if _address not in self._blacklist_address:
                self._blacklist_address.put(_address)

    @external
    def switch_address_update_db(self) -> None:
        """
        Switches the day when the distribution has to be started
        :return:
        """
        if self.msg.sender != self._dividends_score.get():
            revert("This method can only be called by dividends distribution contract")
        new_day = (self._address_update_db.get() + 1) % 2
        self._address_update_db.set(new_day)
        address_changes = self._changes[new_day]
        self._index_address_changes.set(len(address_changes))
