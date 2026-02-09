// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

interface AggregatorV3Interface {
    function decimals() external view returns (uint8);
    function latestRoundData()
        external
        view
        returns (
            uint80 roundId,
            int256 answer,
            uint256 startedAt,
            uint256 updatedAt,
            uint80 answeredInRound
        );
}

/// @notice Chainlink 价格适配器，输出 1e18 精度
contract ChainlinkOracle {
    AggregatorV3Interface public immutable feed;

    constructor(address _feed) {
        require(_feed != address(0), "feed=0");
        feed = AggregatorV3Interface(_feed);
    }

    function getPrice() external view returns (uint256) {
        (, int256 answer,, uint256 updatedAt,) = feed.latestRoundData();
        require(answer > 0, "bad price");
        require(updatedAt > 0, "stale");
        uint8 dec = feed.decimals();
        uint256 price = uint256(answer);
        if (dec < 18) {
            return price * (10 ** (18 - dec));
        }
        if (dec > 18) {
            return price / (10 ** (dec - 18));
        }
        return price;
    }
}
