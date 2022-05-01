import argparse
import os

import numpy as np
import torch
from matplotlib import pyplot as plt
from multiagent import scenarios
from multiagent.environment import MultiAgentEnv

from MADDPG import MADDPG

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('env', type=str, help='name of the environment',
                        choices=['simple_adversary', 'simple_crypto', 'simple_push', 'simple_reference',
                                 'simple_speaker_listener', 'simple_spread', 'simple_tag',
                                 'simple_world_comm'])
    parser.add_argument('--episode-length', type=int, default=100, help='steps per episode')
    parser.add_argument('--episode-num', type=int, default=5000, help='total number of episode')
    parser.add_argument('--gamma', type=float, default=0.95, help='discount factor')
    parser.add_argument('--buffer-capacity', default=int(1e6))
    parser.add_argument('--batch-size', default=1000)
    parser.add_argument('--actor-lr', type=float, default=0.01, help='learning rate of actor')
    parser.add_argument('--critic-lr', type=float, default=0.01, help='learning rate of critic')
    parser.add_argument('--update-interval', type=int, default=100,
                        help='step interval of updating target network')
    parser.add_argument('--tau', type=float, default=0.02, help='soft update parameter')
    args = parser.parse_args()

    # create folder to save result
    env_dir = os.path.join('results', args.env)
    if not os.path.exists(env_dir):
        os.makedirs(env_dir)
    total_files = len([file for file in os.listdir(env_dir)])
    result_dir = os.path.join(env_dir, f'{total_files + 1}')
    os.makedirs(result_dir)

    # create env
    scenario = scenarios.load(f'{args.env}.py').Scenario()
    world = scenario.make_world()
    env = MultiAgentEnv(world, scenario.reset_world, scenario.reward, scenario.observation)

    # get dimension info about observation and action
    obs_dim_list = []
    for obs_space in env.observation_space:  # continuous observation
        obs_dim_list.append(obs_space.shape[0])  # Box
    act_dim_list = []
    for act_space in env.action_space:  # discrete action
        act_dim_list.append(act_space.n)  # Discrete

    maddpg = MADDPG(obs_dim_list, act_dim_list, args.buffer_capacity, args.actor_lr, args.critic_lr)

    total_step = 0
    total_reward = np.zeros((args.episode_num, env.n))  # reward of each agent in each episode
    for episode in range(args.episode_num):
        obs = env.reset()
        # record reward of each agent in this episode
        episode_reward = np.zeros((args.episode_length, env.n))
        for step in range(args.episode_length):  # interact with the env for an episode
            actions = maddpg.select_action(obs, explore=True)
            next_obs, rewards, dones, infos = env.step(actions)
            episode_reward[step] = rewards
            # env.render()
            total_step += 1

            maddpg.add(obs, actions, rewards, next_obs, dones)
            maddpg.learn(args.batch_size, args.gamma)
            # if total_step % args.update_interval == 0:  #
            maddpg.update_target(args.tau)
            obs = next_obs

        # episode finishes
        # calculate cumulative reward of each agent in this episode
        cumulative_reward = episode_reward.sum(axis=0)
        total_reward[episode] = cumulative_reward
        print(f'episode {episode + 1}: cumulative reward: {cumulative_reward}')

    # all episodes performed, training finishes
    # save agent parameters
    torch.save([agent.actor.state_dict() for agent in maddpg.agents], os.path.join(result_dir, 'model.pt'))


    def get_running_reward(reward_array: np.ndarray, window=100):
        """calculate the running reward, i.e. average of last `window` elements from rewards"""
        running_reward = np.zeros_like(reward_array)
        for i in range(window - 1):
            running_reward[i] = np.mean(reward_array[:i + 1])
        for i in range(window - 1, len(reward_array)):
            running_reward[i] = np.mean(reward_array[i - window + 1:i + 1])
        return running_reward


    # plot result
    fig, ax = plt.subplots()
    x = range(1, args.episode_num + 1)
    for agent in range(env.n):
        ax.plot(x, total_reward[:, agent], label=agent)
        ax.plot(x, get_running_reward(total_reward[:, agent]))
    ax.legend()
    ax.set_xlabel('episode')
    ax.set_ylabel('reward')
    title = f'training result of maddpg solve {args.env}'
    ax.set_title(title)
    plt.savefig(os.path.join(result_dir, title))
