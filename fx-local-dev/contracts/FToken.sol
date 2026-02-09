// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract FToken is ERC20, Ownable {
    constructor(string memory name, string memory symbol) ERC20(name, symbol) {
        // 初始供应量为0
    }
    
    // 仅owner可以mint代币，用于FxVaultV1合约
    function mint(address to, uint256 amount) external onlyOwner {
        _mint(to, amount);
    }
    
    // 仅owner可以burn代币，用于FxVaultV1合约
    function burn(address from, uint256 amount) external onlyOwner {
        _burn(from, amount);
    }
}