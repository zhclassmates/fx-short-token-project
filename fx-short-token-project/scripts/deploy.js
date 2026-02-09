// We import the Hardhat Runtime Environment explicitly here.
// This is optional but useful for running the script in a standalone fashion through `node <script>`.
//
// You can also run a script with `npx hardhat run <script>`.
// If you do that, Hardhat will compile your contracts,
// and execute the script.

const hre = require("hardhat");

async function main() {
  // 部署MockCollateralToken
  const MockCollateralToken = await hre.ethers.getContractFactory("MockCollateralToken");
  const mockCollateral = await MockCollateralToken.deploy();
  await mockCollateral.waitForDeployment();
  console.log("MockCollateralToken deployed to:", await mockCollateral.getAddress());

  // 部署FToken
  const FToken = await hre.ethers.getContractFactory("FToken");
  const fToken = await FToken.deploy("f-MockCollateral", "fMCT");
  await fToken.waitForDeployment();
  console.log("FToken deployed to:", await fToken.getAddress());

  // 部署XToken
  const XToken = await hre.ethers.getContractFactory("XToken");
  const xToken = await XToken.deploy("x-MockCollateral", "xMCT");
  await xToken.waitForDeployment();
  console.log("XToken deployed to:", await xToken.getAddress());

  // 部署FxVaultV1
  const FxVaultV1 = await hre.ethers.getContractFactory("FxVaultV1");
  const vault = await FxVaultV1.deploy(
    await mockCollateral.getAddress(),
    await fToken.getAddress(),
    await xToken.getAddress()
  );
  await vault.waitForDeployment();
  console.log("FxVaultV1 deployed to:", await vault.getAddress());

  // 将FToken和XToken的所有权转移给vault
  await fToken.transferOwnership(await vault.getAddress());
  await xToken.transferOwnership(await vault.getAddress());
  console.log("Ownership of FToken and XToken transferred to vault");

  // 为测试目的，给部署者一些MockCollateralToken
  const [deployer] = await hre.ethers.getSigners();
  await mockCollateral.mint(hre.ethers.parseEther("1000"));
  console.log("Deployer received 1000 MCT for testing");
}

// We recommend this pattern to be able to use async/await everywhere
// and properly handle errors.
main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});