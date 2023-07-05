# Controllers

## Launching a Validator in Controller Mode

1. Prepare the hardware for the validator - 32 virtual cores, 64GB of memory, 1TB SSD, fixed IP address, and 1Gb/s internet speed.

   To maintain network stability, it is recommended to place validators in different locations around the world, rather than concentrating them in a single data center. You can use [this site](https://status.toncenter.com/) to determine the load on various locations. According to the map, there is a high load on data centers in Europe, especially in Finland, Germany, and Paris. Therefore, using providers such as Hetzner and OVH is not recommended.

   > Ensure your hardware meets or exceeds the specified configuration. Running the validator on inappropriate hardware can harm the network and result in penalties.
   > Since May 2021, Hetzner has prohibited mining on its servers. This rule currently applies to both PoW and PoS algorithms. Even installing a regular node will be considered a breach of contract.

2. Install and synchronize **mytonctrl** according to the description in [this instruction](https://github.com/ton-blockchain/mytonctrl/blob/master/docs/en/manual-ubuntu.md) — follow **only** paragraphs 1, 2, and 3.

   You can also refer to this [Video Tutorial](https://docs.ton.org/participate/run-nodes/full-node#installation) for additional help.

3. Transfer 1 TON to the validator wallet address, which is displayed in the `wl` list.

4. Use the `aw` command to activate the validator's wallet.

5. Transfer enough TON to the validator wallet address.

6. Enable the ton-http-api service:
	```
	mytonctrl -> installer -> enable THA
	```
	Exit installer mode with `Ctrl+C`

7. Set the liquid pool address, which will lend TON for validation:
   ```
   set liquid_pool_addr <liquid-pool-address>
   ```

8. Set the lending parameters that acceptable to you:
   ```
   set min_loan 41000
   set max_loan 43000
   set max_interest_percent 1.5
   ```

   where 
* `41000` is the minimum loan amount we are willing to receive from the liquid pool,
* `43000` is the maximum loan amount we are willing to receive from the liquid pool,
*   `1.5` 1.5 is the maximum interest rate value for the liquid pool per validation cycle, which we have agreed upon.

9. Display the annual percentage of profit from the liquid pool:
	```
	calculate_annual_controller_percentage
	```

10. Create two controllers with a single command:

   ```
   new_controllers
   ```

11. Enter `controllers_list` to display the controller addresses:

   ```
   controllers_list
   Address                                             Status  Balance
   kf89KYOeRPRRDyjt_3bPsz92cKSghRqw64efNr8mT1eeHDaS    active  0.704345
   kf_lT8QNykLh5PN5ictNX22maiyIf9iK787fXg6nJ_zB-jbN    active  0.720866
   ```

12. Make a validator deposit in each controller:


```
deposit_to_controller kf89KYOeRPRRDyjt_3bPsz92cKSghRqw64efNr8mT1eeHDaS 10000
deposit_to_controller kf_lT8QNykLh5PN5ictNX22maiyIf9iK787fXg6nJ_zB-jbN 10000
```


where `10000` TON is the deposit amount.

13. Get approval for the controllers. Each pool may have its own approval issuance policy, check with the operator.

14. Set controller mode:

 ```bash
 set useController true
 set stake null
 ```

> (!) If you were previously using nominator pools, do not forget to disable them using the `set usePool false` command.


## Switching a Regular Validator to Controller Operating Mode

1. Enter `set stake 0` to stop participating in elections.

2. Wait until both of your deposits have been returned from the Elector.

3. Follow the instructions under "Launching a Validator in Controller Mode", beginning with **Step 6**.