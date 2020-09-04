from iconservice import *

TAG = "TapToken"

DAY_TO_MICROSECOND = 864 * 10 ** 8

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


class Status:
    AVAILABLE = 0
    STAKED = 1
    UNSTAKING = 2
    UNSTAKING_PERIOD = 3


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

    _STAKED_BALANCES = "staked_balances"
    _MINIMUM_STAKE = "minimum_stake"
    _UNSTAKING_PERIOD = "unstaking_period"
    _TOTAL_STAKED_BALANCE = "total_staked_balance"

    _EVEN_DAY_STAKE_CHANGES = "even_day_stake_changes"
    _ODD_DAY_STAKE_CHANGES = "odd_day_stake_changes"
    _STAKE_CHANGES = "stake_changes"
    _INDEX_STAKE_CHANGES = "index_stake_changes"
    _STAKE_UPDATE_DB = "stake_update_db"

    _STAKING_ENABLED = "staking_enabled"
    _SWITCH_DIVS_TO_STAKED_TAP_ENABLED = "switch_divs_to_staked_tap"

    _PAUSED = "paused"
    _PAUSE_WHITELIST = "pause_whitelist"
    _LOCKLIST = "locklist"

    @eventlog(indexed=3)
    def Transfer(self, _from: Address, _to: Address, _value: int, _data: bytes):
        pass

    @eventlog(indexed=1)
    def LocklistAddress(self, address: Address, note: str):
        pass

    @eventlog(indexed=1)
    def WhitelistAddress(self, address: Address, note: str):
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

        self._staked_balances = DictDB(self._STAKED_BALANCES, db, value_type=int, depth=2)
        self._minimum_stake = VarDB(self._MINIMUM_STAKE, db, value_type=int)
        self._unstaking_period = VarDB(self._UNSTAKING_PERIOD, db, value_type=int)
        self._total_staked_balance = VarDB(self._TOTAL_STAKED_BALANCE, db, value_type=int)

        self._even_day_stake_changes = ArrayDB(self._EVEN_DAY_STAKE_CHANGES, db, value_type=Address)
        self._odd_day_stake_changes = ArrayDB(self._ODD_DAY_STAKE_CHANGES, db, value_type=Address)
        self._stake_changes = [
            self._even_day_stake_changes,
            self._odd_day_stake_changes,
        ]

        # To choose between even and odd DBs
        self._stake_update_db = VarDB(self._STAKE_UPDATE_DB, db, value_type=int)

        self._index_stake_changes = VarDB(self._INDEX_STAKE_CHANGES, db, value_type=int)

        self._staking_enabled = VarDB(self._STAKING_ENABLED, db, value_type=bool)
        self._switch_divs_to_staked_tap_enabled = VarDB(self._SWITCH_DIVS_TO_STAKED_TAP_ENABLED, db, value_type=bool)

        # Pausing and locklist, whitelist implementations
        self._paused = VarDB(self._PAUSED, db, value_type=bool)
        self._pause_whitelist = ArrayDB(self._PAUSE_WHITELIST, db, value_type=Address)
        self._locklist = ArrayDB(self._LOCKLIST, db, value_type=Address)

    def on_install(self, _initialSupply: int, _decimals: int) -> None:
        super().on_install()

        if _initialSupply < 0:
            revert("Initial supply cannot be less than zero")

        if _decimals < 0:
            revert("Decimals cannot be less than zero")

        total_supply = _initialSupply * 10 ** _decimals
        Logger.debug(f"on_install: total_supply={total_supply}", TAG)

        self._total_supply.set(total_supply)
        self._decimals.set(_decimals)
        self._balances[self.owner] = total_supply
        self._addresses.put(self.owner)

    def on_update(self) -> None:
        super().on_update()
        self._staking_enabled.set(False)
        self._switch_divs_to_staked_tap_enabled.set(False)
        self._paused.set(False)

    @external
    def untether(self) -> None:
        """
        A function to redefine the value of self.owner once it is possible.
        To be included through an update if it is added to IconService.

        Sets the value of self.owner to the score holding the game treasury.
        """
        if self.tx.origin != self.owner:
            revert(f"Only the owner can call the untether method.")
        pass

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

    @external(readonly=True)
    def available_balanceOf(self, _owner: Address) -> int:
        detail_balance = self.details_balanceOf(_owner)
        return detail_balance["Available balance"]

    @external(readonly=True)
    def staked_balanceOf(self, _owner: Address) -> int:
        return self._staked_balances[_owner][Status.STAKED]

    @external(readonly=True)
    def unstaked_balanceOf(self, _owner: Address) -> int:
        detail_balance = self.details_balanceOf(_owner)
        return detail_balance["Unstaking balance"]

    @external(readonly=True)
    def total_staked_balance(self) -> int:
        return self._total_staked_balance.get()

    @external(readonly=True)
    def staking_enabled(self) -> bool:
        return self._staking_enabled.get()

    @external(readonly=True)
    def switch_divs_to_staked_tap_enabled(self) -> bool:
        return self._switch_divs_to_staked_tap_enabled.get()

    @external(readonly=True)
    def getPaused(self) -> bool:
        return self._paused.get()

    @external(readonly=True)
    def details_balanceOf(self, _owner: Address) -> dict:
        if self._staked_balances[_owner][Status.UNSTAKING_PERIOD] < self.now():
            curr_unstaked = self._staked_balances[_owner][Status.UNSTAKING]
        else:
            curr_unstaked = 0

        if self._first_time(_owner):
            available_balance = self.balanceOf(_owner)
        else:
            available_balance = self._staked_balances[_owner][Status.AVAILABLE]

        unstaking_amount = self._staked_balances[_owner][Status.UNSTAKING] - curr_unstaked
        unstaking_time = 0 if unstaking_amount == 0 else self._staked_balances[_owner][Status.UNSTAKING_PERIOD]
        return {
            "Total balance": self._balances[_owner],
            "Available balance": available_balance + curr_unstaked,
            "Staked balance": self._staked_balances[_owner][Status.STAKED],
            "Unstaking balance": unstaking_amount,
            "Unstaking time (in microseconds)": unstaking_time
        }

    def _first_time(self, _from: Address) -> bool:
        if (
            self._staked_balances[_from][Status.AVAILABLE] == 0
            and self._staked_balances[_from][Status.STAKED] == 0
            and self._staked_balances[_from][Status.UNSTAKING] == 0
            and self._balances[_from] != 0
        ):
            return True
        else:
            return False

    def _check_first_time(self, _from: Address):
        # If first time copy the balance to available staked balances
        if self._first_time(_from):
            self._staked_balances[_from][Status.AVAILABLE] = self._balances[_from]

    def _staking_enabled_only(self):
        if not self._staking_enabled.get():
            revert("Staking must first be enabled.")

    def _switch_divs_to_staked_tap_enabled_only(self):
        if not self._switch_divs_to_staked_tap_enabled.get():
            revert("Switching to dividends for staked tap has to be enabled.")

    @external
    def toggle_staking_enabled(self):
        self._owner_only()
        self._staking_enabled.set(not self._staking_enabled.get())

    @external
    def toggle_switch_divs_to_staked_tap_enabled(self):
        self._owner_only()
        self._switch_divs_to_staked_tap_enabled.set(not self._switch_divs_to_staked_tap_enabled.get())

    @external
    def togglePaused(self) -> None:
        self._owner_only()
        self._paused.set(not self._paused.get())

    @external
    def stake(self, _value: int):
        self._staking_enabled_only()
        _from = self.msg.sender
        if _value < 0:
            revert("Staked TAP value can't be less than zero")
        if _value > self._balances[_from]:
            revert("Out of TAP balance")
        if _value < self._minimum_stake.get() and _value != 0:
            revert("Staked TAP must be greater than the minimum stake amount and non zero")

        self._check_first_time(_from)
        # Check if the unstaking period has already been reached.
        self._makeAvailable(_from)

        if _from in self._locklist:
            revert("Locked address not permitted to stake.")

        old_stake = self._staked_balances[_from][Status.STAKED] + self._staked_balances[_from][Status.UNSTAKING]
        new_stake = _value
        stake_increment = _value - self._staked_balances[_from][Status.STAKED]
        unstake_amount: int = 0
        if new_stake > old_stake:
            offset: int = new_stake - old_stake
            self._staked_balances[_from][Status.AVAILABLE] = self._staked_balances[_from][Status.AVAILABLE] - offset
        else:
            unstake_amount = old_stake - new_stake

        self._staked_balances[_from][Status.STAKED] = _value
        self._staked_balances[_from][Status.UNSTAKING] = unstake_amount
        self._staked_balances[_from][Status.UNSTAKING_PERIOD] = self.now() + self._unstaking_period.get()
        self._total_staked_balance.set(self._total_staked_balance.get() + stake_increment)

        if _from not in self._stake_changes[self._stake_update_db.get()]:
            self._stake_changes[self._stake_update_db.get()].put(_from)

    @external
    def transfer(self, _to: Address, _value: int, _data: bytes = None):
        if self._paused.get() and (self.msg.sender not in self._pause_whitelist):
            revert(f'TAP token transfers are paused.')
        if self.msg.sender in self._locklist:
            revert(f'Transfer of TAP has been locked for this address.')

        if _data is None:
            _data = b"None"
        self._transfer(self.msg.sender, _to, _value, _data)

    def _transfer(self, _from: Address, _to: Address, _value: int, _data: bytes):

        # Checks the sending value and balance.
        if _value < 0:
            revert("Transferring value cannot be less than zero")
        if self._balances[_from] < _value:
            revert("Out of balance")

        self._check_first_time(_from)
        self._check_first_time(_to)
        self._makeAvailable(_to)
        self._makeAvailable(_from)

        if self._staked_balances[_from][Status.AVAILABLE] < _value:
            revert("Out of available balance")

        self._balances[_from] = self._balances[_from] - _value
        self._balances[_to] = self._balances[_to] + _value

        self._staked_balances[_from][Status.AVAILABLE] = (self._staked_balances[_from][Status.AVAILABLE] - _value)
        self._staked_balances[_to][Status.AVAILABLE] = (self._staked_balances[_to][Status.AVAILABLE] + _value)

        if _to not in self._addresses:
            self._addresses.put(_to)

        if _to.is_contract:
            # If the recipient is SCORE,
            #   then calls `tokenFallback` to hand over control.
            recipient_score = self.create_interface_score(_to, TokenFallbackInterface)
            recipient_score.tokenFallback(_from, _value, _data)

        # Emits an event log `Transfer`
        self.Transfer(_from, _to, _value, _data)
        if not self._switch_divs_to_staked_tap_enabled.get():
            address_changes = self._changes[self._address_update_db.get()]
            if _from not in self._blacklist_address:
                address_changes.put(_from)
            if _to not in self._blacklist_address:
                address_changes.put(_to)
        Logger.debug(f"Transfer({_from}, {_to}, {_value}, {_data})", TAG)

    def _owner_only(self):
        if self.msg.sender != self.owner:
            revert("Only owner can call this method")

    def _dividends_only(self):
        if self.msg.sender != self._dividends_score.get():
            revert("This method can only be called by the dividends distribution contract")

    def _makeAvailable(self, _from: Address):
        # Check if the unstaking period has already been reached.
        if self._staked_balances[_from][Status.UNSTAKING_PERIOD] <= self.now():
            curr_unstaked = self._staked_balances[_from][Status.UNSTAKING]
            self._staked_balances[_from][Status.UNSTAKING] = 0
            self._staked_balances[_from][Status.AVAILABLE] += curr_unstaked

    @external
    def set_minimum_stake(self, _amount: int) -> None:
        """
        Set the minimum stake amount
        :param _amount: Minimum amount of stake needed.
        """
        self._owner_only()
        if _amount < 0:
            revert("Amount cannot be less than zero")

        total_amount = _amount * 10 ** self._decimals.get()
        self._minimum_stake.set(total_amount)

    @external
    def set_unstaking_period(self, _time: int) -> None:
        """
        Set the minimum staking period
        :param _time: Staking time period in days.
        """
        self._owner_only()
        if _time < 0:
            revert("Time cannot be negative.")
        total_time = _time * DAY_TO_MICROSECOND  # convert days to microseconds
        self._unstaking_period.set(total_time)

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
    def get_minimum_stake(self) -> int:
        """
        Returns the minimum stake amount
        """
        return self._minimum_stake.get()

    @external(readonly=True)
    def get_unstaking_period(self) -> int:
        """
        Returns the minimum staking period in days
        """
        time_in_microseconds = self._unstaking_period.get()
        time_in_days = time_in_microseconds // DAY_TO_MICROSECOND
        return time_in_days

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
        self._dividends_only()
        balance_changes = self._changes[self._balance_update_db.get()]
        length_list = len(balance_changes)

        start = self._index_update_balance.get()
        if start == length_list:
            if self._balance_update_db.get() != self._address_update_db.get():
                self._balance_update_db.set(self._address_update_db.get())
                self._index_update_balance.set(self._index_address_changes.get())
            return {}
        end = min(start + self._max_loop.get(), length_list)
        balances = {
            str(balance_changes[i]): self._balances[balance_changes[i]]
            for i in range(start, end)
        }
        self._index_update_balance.set(end)
        return balances

    @external
    def clear_yesterdays_changes(self) -> bool:
        """
        Clears the array db storing yesterday's changes
        :return: True if the array has been emptied
        """
        self._dividends_only()
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
                revert(f"{_address} not in blacklist address")
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
        self._dividends_only()
        new_day = (self._address_update_db.get() + 1) % 2
        self._address_update_db.set(new_day)
        address_changes = self._changes[new_day]
        self._index_address_changes.set(len(address_changes))

    @external
    def get_stake_updates(self) -> dict:
        """
        Returns the updated addresses. Returns empty dictionary if the updates has
        completed
        :return: Dictionary contains the addresses. Maximum number of addresses
        and balances returned is defined by the max_loop
        """
        self._dividends_only()
        self._staking_enabled_only()
        self._switch_divs_to_staked_tap_enabled_only()

        stake_changes = self._stake_changes[self._stake_update_db.get()]
        length_list = len(stake_changes)

        start = self._index_stake_changes.get()
        if start == length_list:
            return {}
        end = min(start + self._max_loop.get(), length_list)
        detailed_balances = {
            str(stake_changes[i]): self.staked_balanceOf(stake_changes[i])
            for i in range(start, end)
        }
        self._index_stake_changes.set(end)
        return detailed_balances

    @external
    def switch_stake_update_db(self) -> None:
        self._dividends_only()
        self._staking_enabled_only()
        self._switch_divs_to_staked_tap_enabled_only()

        new_day = (self._stake_update_db.get() + 1) % 2
        self._stake_update_db.set(new_day)
        stake_changes = self._stake_changes[new_day]
        self._index_stake_changes.set(len(stake_changes))

    @external
    def clear_yesterdays_stake_changes(self) -> bool:
        self._staking_enabled_only()
        self._switch_divs_to_staked_tap_enabled_only()
        self._dividends_only()
        yesterday = (self._stake_update_db.get() + 1) % 2
        yesterdays_changes = self._stake_changes[yesterday]
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
    def get_locklist_addresses(self) -> list:
        """
        Returns all locked addresses.
        :return: List of locked addresses
        :rtype: list
        """
        address_list = []
        for address in self._locklist:
            address_list.append(address)
        return address_list

    @external
    def remove_from_locklist(self, _address: Address) -> None:
        """
        Removes the address from the locklist.
        Only owner can remove the locklist address
        :param _address: Address to be removed from locklist
        :type _address: :class:`iconservice.base.address.Address`
        :return:
        """
        self._owner_only()
        if _address not in self._locklist:
            revert(f'{_address} not in locklist address')
        self.LocklistAddress(_address, "Removed from Locklist")
        top = self._locklist.pop()
        if top != _address:
            for i in range(len(self._locklist)):
                if self._locklist[i] == _address:
                    self._locklist[i] = top

    @external
    def set_locklist_address(self, _address: Address) -> None:
        """
        Add address to list of addresses that cannot transfer TAP.
        Only the owner can set the locklist address
        :param _address: Address to be included in the locklist
        :type _address: :class:`iconservice.base.address.Address`
        :return:
        """
        self._owner_only()
        self._staking_enabled_only()

        self.LocklistAddress(_address, "Added to Locklist")
        if _address not in self._locklist:
            self._locklist.put(_address)

        # Unstake TAP of locklist address
        staked_balance = self._staked_balances[_address][Status.STAKED]
        if staked_balance > 0:
            # Check if the unstaking period has already been reached.
            self._makeAvailable(_address)
            self._staked_balances[_address][Status.STAKED] = 0
            self._staked_balances[_address][Status.UNSTAKING] += staked_balance
            self._staked_balances[_address][Status.UNSTAKING_PERIOD] = (self.now() + self._unstaking_period.get())
            self._total_staked_balance.set(self._total_staked_balance.get() - staked_balance)
            if _address not in self._stake_changes[self._stake_update_db.get()]:
                self._stake_changes[self._stake_update_db.get()].put(_address)

    @external(readonly=True)
    def get_whitelist_addresses(self) -> list:
        """
        Returns all addresses whitelisted during pause.
        :return: List of whitelisted addresses
        :rtype: list
        """
        address_list = []
        for address in self._pause_whitelist:
            address_list.append(address)
        return address_list

    @external
    def remove_from_whitelist(self, _address: Address) -> None:
        """
        Removes the address from whitelist.
        Only owner can remove the whitelist address
        :param _address: Address to be removed from whitelist
        :type _address: :class:`iconservice.base.address.Address`
        :return:
        """
        self._owner_only()
        if _address not in self._pause_whitelist:
            revert(f'{_address} not in whitelist address')
        self.WhitelistAddress(_address, "Removed from whitelist")
        top = self._pause_whitelist.pop()
        if top != _address:
            for i in range(len(self._pause_whitelist)):
                if self._pause_whitelist[i] == _address:
                    self._pause_whitelist[i] = top

    @external
    def set_whitelist_address(self, _address: Address) -> None:
        """
        Add address to list of addresses exempt from transfer pause.
        Only the owner can set the whitelist address
        :param _address: Address to be included in the whitelist
        :type _address: :class:`iconservice.base.address.Address`
        :return:
        """
        self._owner_only()
        self.WhitelistAddress(_address, "Added to Pause Whitelist")
        if _address not in self._pause_whitelist:
            self._pause_whitelist.put(_address)
