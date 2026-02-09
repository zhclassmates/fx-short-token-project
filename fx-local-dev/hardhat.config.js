require("@nomiclabs/hardhat-waffle");

module.exports = {
  solidity: "0.8.24",  // Solidity 版本
  networks: {
    hardhat: {  // 本地网络
      chainId: 31337,
    },
  },
};