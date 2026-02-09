// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title MockPriceOracle
 * @notice 用于测试的价格预言机
 */
contract MockPriceOracle {
    uint256 public price;
    uint8 public decimals;
    
    event PriceUpdated(uint256 oldPrice, uint256 newPrice);
    
    constructor(uint256 _initialPrice) {
        price = _initialPrice;
        decimals = 18;
    }
    
    /**
     * @notice 获取当前价格
     */
    function getPrice() external view returns (uint256) {
        return price;
    }
    
    /**
     * @notice 设置新价格（仅用于测试）
     */
    function setPrice(uint256 newPrice) external {
        uint256 oldPrice = price;
        price = newPrice;
        emit PriceUpdated(oldPrice, newPrice);
    }
    
    /**
     * @notice 模拟价格波动
     * @param changePercent 变动百分比（1e18 = 100%）
     * @param isIncrease 是否上涨
     */
    function simulatePriceChange(uint256 changePercent, bool isIncrease) external {
        uint256 oldPrice = price;
        if (isIncrease) {
            price = price * (1e18 + changePercent) / 1e18;
        } else {
            price = price * (1e18 - changePercent) / 1e18;
        }
        emit PriceUpdated(oldPrice, price);
    }
}
